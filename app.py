import streamlit as st
from supabase import create_client, Client
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
import hashlib
import hmac
import secrets
import re


# ============================================================
# CONFIGURAZIONE PAGINA
# ============================================================

st.set_page_config(
    page_title="Gestione Ticket",
    page_icon="🎫",
    layout="wide"
)


# ============================================================
# COLLEGAMENTO SUPABASE
# ============================================================

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


try:
    supabase = get_supabase()
except Exception as e:
    st.error("❌ Errore collegamento a Supabase")
    st.exception(e)
    st.stop()


# ============================================================
# SESSION STATE
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "ruolo" not in st.session_state:
    st.session_state.ruolo = ""

if "pagina" not in st.session_state:
    st.session_state.pagina = "Dashboard"


# ============================================================
# FUNZIONI UTILI
# ============================================================

def is_admin():
    ruolo = st.session_state.get("ruolo", "").strip().lower()
    return ruolo == "amministratore"


# ============================================================
# SICUREZZA PASSWORD
# ============================================================

def genera_hash_password(password):
    """Genera un hash PBKDF2-HMAC-SHA256 con salt casuale."""
    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000
    )

    return f"{salt.hex()}${password_hash.hex()}"


def verifica_password(password, password_salvata):
    """
    Verifica la password.
    Supporta temporaneamente anche le vecchie password in chiaro
    per consentire la migrazione automatica al primo accesso.
    """
    if not password_salvata:
        return False

    if "$" in password_salvata:
        try:
            salt_hex, hash_salvato = password_salvata.split("$", 1)
            salt = bytes.fromhex(salt_hex)

            nuovo_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                200_000
            ).hex()

            return hmac.compare_digest(nuovo_hash, hash_salvato)

        except Exception:
            return False

    # Compatibilità temporanea con password precedenti in chiaro
    return hmac.compare_digest(password, password_salvata)


def password_da_migrare(password_salvata):
    return bool(password_salvata and "$" not in password_salvata)


def valida_password(password):
    """
    Regole:
    - almeno 8 caratteri
    - almeno una maiuscola
    - almeno una minuscola
    - almeno un numero
    """
    errori = []

    if len(password) < 8:
        errori.append("Almeno 8 caratteri.")

    if not re.search(r"[A-Z]", password):
        errori.append("Almeno una lettera maiuscola.")

    if not re.search(r"[a-z]", password):
        errori.append("Almeno una lettera minuscola.")

    if not re.search(r"\d", password):
        errori.append("Almeno un numero.")

    return errori


def mostra_regole_password():
    st.caption(
        "La password deve contenere almeno 8 caratteri, "
        "una maiuscola, una minuscola e un numero."
    )


def format_data(data):
    if not data:
        return ""

    try:
        return str(data).replace("T", " ")[:19]
    except:
        return str(data)


def get_tickets():
    try:
        risposta = (
            supabase
            .table("tickets")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        return risposta.data or []

    except Exception as e:
        st.error(f"Errore caricamento ticket: {e}")
        return []


def get_ticket(ticket_id):
    try:
        risposta = (
            supabase
            .table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .execute()
        )

        if risposta.data:
            return risposta.data[0]

        return None

    except Exception as e:
        st.error(f"Errore caricamento ticket: {e}")
        return None


# ============================================================
# GESTIONE CATEGORIE
# ============================================================

def get_categorie(solo_attive=True):
    try:
        query = (
            supabase
            .table("categorie")
            .select("*")
            .order("nome")
        )

        if solo_attive:
            query = query.eq("attivo", True)

        risposta = query.execute()
        return risposta.data or []

    except Exception as e:
        st.error(f"Errore caricamento categorie: {e}")
        return []


def get_nomi_categorie_attive():
    categorie = get_categorie(solo_attive=True)
    return [categoria.get("nome", "") for categoria in categorie]


def aggiungi_categoria(nome):
    try:
        nome = nome.strip()

        if not nome:
            return False, "Inserisci il nome della categoria."

        (
            supabase
            .table("categorie")
            .insert({
                "nome": nome,
                "attivo": True
            })
            .execute()
        )

        return True, "Categoria aggiunta correttamente."

    except Exception as e:
        messaggio = str(e)

        if "duplicate" in messaggio.lower() or "unique" in messaggio.lower():
            return False, "Esiste già una categoria con questo nome."

        return False, f"Errore: {e}"


def modifica_categoria(categoria_id, vecchio_nome, nuovo_nome):
    try:
        nuovo_nome = nuovo_nome.strip()

        if not nuovo_nome:
            return False, "Il nome della categoria non può essere vuoto."

        if nuovo_nome == vecchio_nome:
            return False, "Il nuovo nome è uguale a quello attuale."

        (
            supabase
            .table("categorie")
            .update({"nome": nuovo_nome})
            .eq("id", categoria_id)
            .execute()
        )

        # Mantiene coerenti anche i ticket già creati.
        (
            supabase
            .table("tickets")
            .update({"categoria": nuovo_nome})
            .eq("categoria", vecchio_nome)
            .execute()
        )

        return True, "Categoria modificata e ticket aggiornati."

    except Exception as e:
        messaggio = str(e)

        if "duplicate" in messaggio.lower() or "unique" in messaggio.lower():
            return False, "Esiste già una categoria con questo nome."

        return False, f"Errore: {e}"


def cambia_stato_categoria(categoria_id, attivo):
    try:
        (
            supabase
            .table("categorie")
            .update({"attivo": attivo})
            .eq("id", categoria_id)
            .execute()
        )

        return True, "Stato categoria aggiornato."

    except Exception as e:
        return False, f"Errore: {e}"


def get_messaggi(ticket_id):
    try:
        risposta = (
            supabase
            .table("ticket_messaggi")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("data_messaggio")
            .execute()
        )

        return risposta.data or []

    except Exception as e:
        st.error(f"Errore caricamento messaggi: {e}")
        return []


def get_allegati(ticket_id):
    try:
        risposta = (
            supabase
            .table("ticket_allegati")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("data_caricamento", desc=True)
            .execute()
        )

        return risposta.data or []

    except Exception as e:
        st.error(f"Errore caricamento allegati: {e}")
        return []


# ============================================================
# LOGIN
# ============================================================

def pagina_login():

    st.title("🎫 Gestione Ticket")
    st.write("Accedi al sistema")

    with st.form("form_login"):

        username = st.text_input("Username")

        password = st.text_input(
            "Password",
            type="password"
        )

        login = st.form_submit_button(
            "🔐 Accedi",
            use_container_width=True
        )

    if login:

        username = username.strip()

        if not username or not password:
            st.warning("Inserisci username e password.")
            return

        try:

            # Cerchiamo l'utente, senza confrontare la password nel database.
            risposta = (
                supabase
                .table("utenti")
                .select("*")
                .eq("username", username)
                .execute()
            )

            if not risposta.data:
                st.error("❌ Username o password non corretti.")
                return

            utente = risposta.data[0]

            # Se la colonna attivo è presente, impedisce il login
            # agli account disattivati. Per i vecchi record senza colonna
            # viene considerato attivo per compatibilità.
            if utente.get("attivo", True) is False:
                st.error("⛔ Questo account è stato disattivato.")
                return

            password_salvata = utente.get("password", "")

            if not verifica_password(password, password_salvata):
                st.error("❌ Username o password non corretti.")
                return

            # Migrazione automatica delle vecchie password in chiaro.
            if password_da_migrare(password_salvata):

                nuovo_hash = genera_hash_password(password)

                (
                    supabase
                    .table("utenti")
                    .update({"password": nuovo_hash})
                    .eq("id", utente["id"])
                    .execute()
                )

            st.session_state.logged_in = True
            st.session_state.username = utente["username"]
            st.session_state.ruolo = utente.get("ruolo", "")

            st.success("✅ Login effettuato!")
            st.rerun()

        except Exception as e:
            st.error(f"Errore login: {e}")


# ============================================================
# CREAZIONE TICKET
# ============================================================

def pagina_nuovo_ticket():

    st.title("➕ Nuovo Ticket")

    with st.form("nuovo_ticket_form"):

        titolo = st.text_input("Titolo del problema")

        descrizione = st.text_area(
            "Descrizione",
            height=150
        )

        col1, col2 = st.columns(2)

        with col1:

            categorie_attive = get_nomi_categorie_attive()

            if not categorie_attive:

                st.warning(
                    "⚠️ Non sono disponibili categorie attive. "
                    "Contatta l'amministratore."
                )

                categoria = None

            else:

                categoria = st.selectbox(
                    "Categoria",
                    categorie_attive
                )

        with col2:

            priorita = st.selectbox(
                "Priorità",
                [
                    "Bassa",
                    "Media",
                    "Alta",
                    "Urgente"
                ]
            )

        st.divider()

        st.subheader("📎 Allegati")

        st.write("Puoi caricare un file dalla galleria oppure usare la fotocamera.")

        allegati = st.file_uploader(
            "📁 Seleziona file dalla galleria",
            accept_multiple_files=True,
            type=[
                "jpg",
                "jpeg",
                "png",
                "pdf",
                "doc",
                "docx"
            ]
        )

        foto = st.camera_input(
            "📷 Scatta una foto"
        )

        invia = st.form_submit_button(
            "🎫 Crea Ticket",
            use_container_width=True
        )

    if invia:

        if not titolo.strip():
            st.warning("Inserisci il titolo del ticket.")
            return

        if not categoria:
            st.warning("Seleziona una categoria valida.")
            return

        if not descrizione.strip():
            st.warning("Inserisci una descrizione.")
            return

        try:

            dati_ticket = {
                "titolo": titolo,
                "descrizione": descrizione,
                "categoria": categoria,
                "priorita": priorita,
                "stato": "Aperto",
                "creato_da": st.session_state.username
            }

            risposta = (
                supabase
                .table("tickets")
                .insert(dati_ticket)
                .execute()
            )

            if not risposta.data:
                st.error("Errore durante la creazione del ticket.")
                return

            ticket_creato = risposta.data[0]
            ticket_id = ticket_creato["id"]

            # ------------------------------------------------
            # ALLEGATI DALLA GALLERIA
            # ------------------------------------------------

            if allegati:

                for file in allegati:

                    salva_allegato(
                        ticket_id,
                        file
                    )

            # ------------------------------------------------
            # FOTO FOTOCAMERA
            # ------------------------------------------------

            if foto:

                salva_allegato(
                    ticket_id,
                    foto
                )

            st.success(
                f"✅ Ticket #{ticket_id} creato correttamente!"
            )

            st.balloons()

        except Exception as e:

            st.error(f"Errore: {e}")


# ============================================================
# SALVATAGGIO ALLEGATI
# ============================================================

def salva_allegato(ticket_id, file):
    try:
        nome_file = file.name
        tipo_file = getattr(file, "type", "application/octet-stream")
        percorso_file = f"ticket_{ticket_id}/{nome_file}"
        contenuto = file.getvalue()

        supabase.storage.from_("allegati").upload(
            path=percorso_file,
            file=contenuto,
            file_options={"content-type": tipo_file, "upsert": "true"}
        )

        supabase.table("ticket_allegati").insert({
            "ticket_id": ticket_id,
            "nome_file": nome_file,
            "percorso_file": percorso_file,
            "tipo_file": tipo_file
        }).execute()

    except Exception as e:
        st.warning(f"Impossibile salvare allegato {file.name}: {e}")


def scarica_allegato(percorso_file):
    try:
        return supabase.storage.from_("allegati").download(percorso_file)
    except Exception:
        return None


# ============================================================
# ELIMINAZIONE COMPLETA TICKET
# ============================================================

def elimina_ticket_completo(ticket_id):
    """
    Elimina definitivamente:
    - file degli allegati dallo Storage
    - record degli allegati
    - messaggi del ticket
    - ticket principale
    """

    try:

        allegati = get_allegati(ticket_id)

        percorsi_file = [
            allegato.get("percorso_file")
            for allegato in allegati
            if allegato.get("percorso_file")
        ]

        # 1. Elimina i file dal Supabase Storage
        if percorsi_file:

            try:
                supabase.storage.from_("allegati").remove(
                    percorsi_file
                )

            except Exception as e:
                raise Exception(
                    "Impossibile eliminare gli allegati dallo Storage. "
                    f"Il ticket non è stato cancellato. Dettaglio: {e}"
                )

        # 2. Elimina i record degli allegati
        (
            supabase
            .table("ticket_allegati")
            .delete()
            .eq("ticket_id", ticket_id)
            .execute()
        )

        # 3. Elimina i messaggi collegati
        (
            supabase
            .table("ticket_messaggi")
            .delete()
            .eq("ticket_id", ticket_id)
            .execute()
        )

        # 4. Elimina il ticket
        (
            supabase
            .table("tickets")
            .delete()
            .eq("id", ticket_id)
            .execute()
        )

        return True, "Ticket eliminato completamente."

    except Exception as e:
        return False, str(e)


# ============================================================
# DETTAGLIO TICKET
# ============================================================

def mostra_ticket(ticket):

    ticket_id = ticket["id"]

    chiuso = ticket.get("stato") == "Chiuso"

    with st.expander(
        f"🎫 #{ticket_id} - {ticket['titolo']} | {ticket['stato']}",
        expanded=False
    ):

        col1, col2, col3 = st.columns(3)

        with col1:
            st.write(f"**Categoria:** {ticket.get('categoria', '')}")

        with col2:
            st.write(f"**Priorità:** {ticket.get('priorita', '')}")

        with col3:
            st.write(f"**Stato:** {ticket.get('stato', '')}")

        st.write(
            f"**Creato da:** {ticket.get('creato_da', '')}"
        )

        st.write("### 📝 Descrizione")

        st.write(ticket.get("descrizione", ""))

        st.divider()

        # ====================================================
        # MESSAGGI
        # ====================================================

        st.subheader("💬 Conversazione")

        messaggi = get_messaggi(ticket_id)

        if messaggi:

            for messaggio in messaggi:

                autore = messaggio.get("autore", "")
                testo = messaggio.get("messaggio", "")
                data = format_data(
                    messaggio.get("data_messaggio")
                )

                if autore == st.session_state.username:

                    st.info(
                        f"**Tu - {data}**\n\n{testo}"
                    )

                else:

                    st.success(
                        f"**{autore} - {data}**\n\n{testo}"
                    )

        else:
            st.info("Nessun messaggio presente.")

        # ====================================================
        # SE TICKET APERTO → MESSAGGI POSSIBILI
        # ====================================================

        if not chiuso:

            nuovo_messaggio = st.text_area(
                "Scrivi un messaggio",
                key=f"msg_{ticket_id}"
            )

            if st.button(
                "📨 Invia messaggio",
                key=f"send_{ticket_id}"
            ):

                if nuovo_messaggio.strip():

                    try:

                        (
                            supabase
                            .table("ticket_messaggi")
                            .insert({
                                "ticket_id": ticket_id,
                                "autore": st.session_state.username,
                                "messaggio": nuovo_messaggio
                            })
                            .execute()
                        )

                        st.success("Messaggio inviato!")

                        st.rerun()

                    except Exception as e:

                        st.error(f"Errore invio messaggio: {e}")

                else:

                    st.warning("Scrivi un messaggio.")

        else:

            st.warning(
                "🔒 Questo ticket è chiuso e non può più essere modificato."
            )

        st.divider()

        # ====================================================
        # ALLEGATI
        # ====================================================

        st.subheader("📎 Allegati")

        allegati = get_allegati(ticket_id)

        if allegati:

            for allegato in allegati:

                st.write(
                    f"📄 **{allegato.get('nome_file', '')}**"
                )

                st.caption(
                    allegato.get("tipo_file", "")
                )

        else:

            st.info("Nessun allegato.")

        st.divider()

        # ====================================================
        # AZIONI AMMINISTRATORE
        # ====================================================

        if is_admin():

            col_admin1, col_admin2, col_admin3 = st.columns(3)

            # ====================================================
            # CHIUSURA
            # ====================================================

            with col_admin1:

                if not chiuso:

                    if st.button(
                        "🔒 Chiudi Ticket",
                        key=f"close_{ticket_id}",
                        use_container_width=True
                    ):

                        try:

                            (
                                supabase
                                .table("tickets")
                                .update({
                                    "stato": "Chiuso"
                                })
                                .eq("id", ticket_id)
                                .execute()
                            )

                            st.success(
                                "Ticket chiuso e archiviato!"
                            )

                            st.rerun()

                        except Exception as e:

                            st.error(f"Errore: {e}")

                else:

                    st.success(
                        "📁 Ticket archiviato"
                    )

            # ====================================================
            # PDF
            # ====================================================

            with col_admin2:

                pdf = genera_pdf(ticket)

                st.download_button(
                    label="📄 Scarica PDF",
                    data=pdf,
                    file_name=f"ticket_{ticket_id}.pdf",
                    mime="application/pdf",
                    key=f"pdf_{ticket_id}",
                    use_container_width=True
                )

            # ====================================================
            # ELIMINAZIONE PROTETTA
            # ====================================================

            with col_admin3:

                with st.expander(
                    "🗑️ Elimina Ticket",
                    expanded=False
                ):

                    st.error(
                        "⚠️ Operazione irreversibile."
                    )

                    st.caption(
                        "Verranno eliminati il ticket, "
                        "tutti i messaggi e tutti gli allegati."
                    )

                    conferma_eliminazione = st.text_input(
                        "Scrivi ELIMINA per confermare",
                        key=f"confirm_delete_{ticket_id}"
                    )

                    if st.button(
                        "🗑️ Elimina definitivamente",
                        key=f"delete_{ticket_id}",
                        use_container_width=True
                    ):

                        if conferma_eliminazione.strip() != "ELIMINA":

                            st.warning(
                                "Per confermare devi scrivere esattamente: ELIMINA"
                            )

                        else:

                            successo, messaggio = (
                                elimina_ticket_completo(ticket_id)
                            )

                            if successo:

                                st.success(
                                    f"✅ Ticket #{ticket_id} eliminato definitivamente."
                                )

                                st.rerun()

                            else:

                                st.error(
                                    f"❌ Errore durante l'eliminazione: {messaggio}"
                                )


# ============================================================
# GENERAZIONE PDF
# ============================================================

def genera_pdf(ticket):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4
    )

    elementi = []

    styles = getSampleStyleSheet()

    titolo = Paragraph(
        f"Ticket #{ticket['id']} - {ticket['titolo']}",
        styles["Title"]
    )

    elementi.append(titolo)

    elementi.append(Spacer(1, 20))

    dati = [

        ["Categoria", ticket.get("categoria", "")],
        ["Priorità", ticket.get("priorita", "")],
        ["Stato", ticket.get("stato", "")],
        ["Creato da", ticket.get("creato_da", "")]
    ]

    tabella = Table(
        dati,
        colWidths=[150, 350]
    )

    tabella.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 8)
        ])
    )

    elementi.append(tabella)

    elementi.append(Spacer(1, 20))

    elementi.append(
        Paragraph(
            "Descrizione",
            styles["Heading2"]
        )
    )

    elementi.append(
        Paragraph(
            ticket.get("descrizione", ""),
            styles["BodyText"]
        )
    )

    elementi.append(Spacer(1, 20))

    # --------------------------------------------------------
    # MESSAGGI NEL PDF
    # --------------------------------------------------------

    messaggi = get_messaggi(ticket["id"])

    if messaggi:

        elementi.append(
            Paragraph(
                "Conversazione",
                styles["Heading2"]
            )
        )

        for messaggio in messaggi:

            testo = (
                f"<b>{messaggio.get('autore', '')}</b> "
                f"({format_data(messaggio.get('data_messaggio'))})"
                f"<br/>{messaggio.get('messaggio', '')}"
            )

            elementi.append(
                Paragraph(
                    testo,
                    styles["BodyText"]
                )
            )

            elementi.append(
                Spacer(1, 10)
            )

    # --------------------------------------------------------
    # FOTO ALLEGATE NEL PDF
    # --------------------------------------------------------
    allegati = get_allegati(ticket["id"])
    immagini_aggiunte = False

    for allegato in allegati:
        tipo_file = allegato.get("tipo_file", "")
        nome_file = allegato.get("nome_file", "")
        percorso_file = allegato.get("percorso_file", "")

        if tipo_file.startswith("image/") and percorso_file:
            contenuto = scarica_allegato(percorso_file)

            if contenuto:
                if not immagini_aggiunte:
                    elementi.append(Paragraph("Foto allegate", styles["Heading2"]))
                    elementi.append(Spacer(1, 10))
                    immagini_aggiunte = True

                try:
                    immagine_buffer = BytesIO(contenuto)
                    image_reader = ImageReader(immagine_buffer)
                    larghezza, altezza = image_reader.getSize()

                    max_larghezza = 500
                    max_altezza = 600
                    rapporto = min(
                        max_larghezza / larghezza,
                        max_altezza / altezza,
                        1
                    )

                    elementi.append(Paragraph(nome_file, styles["BodyText"]))
                    elementi.append(Spacer(1, 5))
                    elementi.append(
                        RLImage(
                            BytesIO(contenuto),
                            width=larghezza * rapporto,
                            height=altezza * rapporto
                        )
                    )
                    elementi.append(Spacer(1, 15))

                except Exception as e:
                    elementi.append(
                        Paragraph(
                            f"Impossibile inserire l'immagine {nome_file}: {e}",
                            styles["BodyText"]
                        )
                    )

    doc.build(elementi)

    buffer.seek(0)

    return buffer.getvalue()


# ============================================================
# DASHBOARD
# ============================================================

def pagina_dashboard():

    st.title("🏠 Dashboard")

    tickets = get_tickets()

    aperti = len([
        t for t in tickets
        if t.get("stato") == "Aperto"
    ])

    lavorazione = len([
        t for t in tickets
        if t.get("stato") == "In lavorazione"
    ])

    chiusi = len([
        t for t in tickets
        if t.get("stato") == "Chiuso"
    ])

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("🎫 Totali", len(tickets))
    col2.metric("🟢 Aperti", aperti)
    col3.metric("🟠 In lavorazione", lavorazione)
    col4.metric("🔒 Archiviati", chiusi)

    st.divider()

    st.subheader("🎫 Ticket recenti")

    recenti = tickets[:5]

    if recenti:

        for ticket in recenti:
            mostra_ticket(ticket)

    else:

        st.info("Non ci sono ancora ticket.")


# ============================================================
# TICKET ATTIVI
# ============================================================

def pagina_ticket():

    st.title("🎫 Ticket Gestiti")

    tickets = get_tickets()

    attivi = [
        t for t in tickets
        if t.get("stato") != "Chiuso"
    ]

    if not attivi:

        st.info("Nessun ticket attivo.")

        return

    for ticket in attivi:

        mostra_ticket(ticket)


# ============================================================
# ARCHIVIO
# ============================================================

def pagina_archivio():

    st.title("📁 Archivio")

    st.write(
        "I ticket chiusi sono archiviati. Solo l'amministratore può eliminarli definitivamente."
    )

    tickets = get_tickets()

    archiviati = [
        t for t in tickets
        if t.get("stato") == "Chiuso"
    ]

    if not archiviati:

        st.info("📭 L'archivio è vuoto.")

        return

    for ticket in archiviati:

        mostra_ticket(ticket)


# ============================================================
# CAMBIO PASSWORD PERSONALE
# ============================================================

def pagina_password():

    st.title("🔐 La mia Password")

    mostra_regole_password()

    with st.form("form_cambio_password_personale"):

        password_attuale = st.text_input(
            "Password attuale",
            type="password"
        )

        nuova_password = st.text_input(
            "Nuova password",
            type="password"
        )

        conferma_password = st.text_input(
            "Conferma nuova password",
            type="password"
        )

        salva = st.form_submit_button(
            "🔒 Salva nuova password",
            use_container_width=True
        )

    if not salva:
        return

    if not password_attuale or not nuova_password or not conferma_password:
        st.warning("⚠️ Compila tutti i campi.")
        return

    if nuova_password != conferma_password:
        st.error("❌ Le nuove password non coincidono.")
        return

    errori = valida_password(nuova_password)

    if errori:
        st.error("❌ La nuova password non soddisfa i requisiti:")
        for errore in errori:
            st.write(f"• {errore}")
        return

    try:

        risposta = (
            supabase
            .table("utenti")
            .select("*")
            .eq("username", st.session_state.username)
            .execute()
        )

        if not risposta.data:
            st.error("❌ Utente non trovato.")
            return

        utente = risposta.data[0]

        if not verifica_password(
            password_attuale,
            utente.get("password", "")
        ):
            st.error("❌ La password attuale non è corretta.")
            return

        if hmac.compare_digest(password_attuale, nuova_password):
            st.warning("⚠️ La nuova password deve essere diversa da quella attuale.")
            return

        nuovo_hash = genera_hash_password(nuova_password)

        (
            supabase
            .table("utenti")
            .update({"password": nuovo_hash})
            .eq("id", utente["id"])
            .execute()
        )

        st.success("✅ Password modificata correttamente!")

    except Exception as e:
        st.error(f"Errore durante il cambio password: {e}")


# ============================================================
# GESTIONE UTENTI AMMINISTRATORE
# ============================================================

def sezione_gestione_utenti():

    st.subheader("👥 Gestione Utenti")

    # --------------------------------------------------------
    # CREAZIONE NUOVO UTENTE
    # --------------------------------------------------------

    with st.expander("➕ Crea nuovo utente", expanded=False):

        with st.form("form_crea_utente"):

            nuovo_username = st.text_input("Username nuovo utente")

            nuova_password = st.text_input(
                "Password iniziale",
                type="password"
            )

            ruolo = st.selectbox(
                "Ruolo",
                ["amministratore", "tecnico"]
            )

            mostra_regole_password()

            crea_utente = st.form_submit_button(
                "➕ Crea utente",
                use_container_width=True
            )

        if crea_utente:

            nuovo_username = nuovo_username.strip()

            if not nuovo_username:
                st.warning("Inserisci uno username.")
                return

            if " " in nuovo_username:
                st.warning("Lo username non può contenere spazi.")
                return

            errori = valida_password(nuova_password)

            if errori:
                st.error("❌ Password non valida:")
                for errore in errori:
                    st.write(f"• {errore}")
                return

            try:

                controllo = (
                    supabase
                    .table("utenti")
                    .select("id")
                    .eq("username", nuovo_username)
                    .execute()
                )

                if controllo.data:
                    st.error("❌ Username già esistente.")
                    return

                password_hash = genera_hash_password(nuova_password)

                (
                    supabase
                    .table("utenti")
                    .insert({
                        "username": nuovo_username,
                        "password": password_hash,
                        "ruolo": ruolo,
                        "attivo": True
                    })
                    .execute()
                )

                st.success("✅ Utente creato correttamente!")
                st.rerun()

            except Exception as e:
                st.error(f"Errore creazione utente: {e}")

    st.divider()
    st.subheader("📋 Utenti registrati")

    try:

        risposta = (
            supabase
            .table("utenti")
            .select("*")
            .order("username")
            .execute()
        )

        utenti = risposta.data or []

        if not utenti:
            st.info("Nessun utente trovato.")
            return

        for utente in utenti:

            user_id = utente.get("id")
            username = utente.get("username", "")
            ruolo = utente.get("ruolo", "")
            attivo = utente.get("attivo", True)

            stato = "🟢 Attivo" if attivo else "🔴 Disattivato"

            with st.expander(
                f"👤 {username} | {ruolo} | {stato}"
            ):

                col1, col2, col3 = st.columns(3)

                # ------------------------------------------------
                # RESET PASSWORD
                # ------------------------------------------------

                with col1:

                    st.write("### 🔑 Reset Password")

                    nuova_pw_admin = st.text_input(
                        "Nuova password",
                        type="password",
                        key=f"reset_pw_{user_id}"
                    )

                    if st.button(
                        "🔑 Reimposta",
                        key=f"reset_btn_{user_id}",
                        use_container_width=True
                    ):

                        if not nuova_pw_admin:
                            st.warning("Inserisci una nuova password.")

                        else:

                            errori = valida_password(nuova_pw_admin)

                            if errori:
                                st.error("❌ Password non valida:")
                                for errore in errori:
                                    st.write(f"• {errore}")

                            else:

                                try:

                                    nuovo_hash = genera_hash_password(
                                        nuova_pw_admin
                                    )

                                    (
                                        supabase
                                        .table("utenti")
                                        .update({
                                            "password": nuovo_hash
                                        })
                                        .eq("id", user_id)
                                        .execute()
                                    )

                                    st.success(
                                        "✅ Password reimpostata correttamente!"
                                    )

                                except Exception as e:
                                    st.error(f"Errore reset password: {e}")

                # ------------------------------------------------
                # MODIFICA RUOLO
                # ------------------------------------------------

                with col2:

                    st.write("### 👔 Ruolo")

                    ruoli = ["amministratore", "tecnico"]

                    indice_ruolo = (
                        ruoli.index(ruolo)
                        if ruolo in ruoli
                        else 1
                    )

                    nuovo_ruolo = st.selectbox(
                        "Seleziona ruolo",
                        ruoli,
                        index=indice_ruolo,
                        key=f"role_{user_id}"
                    )

                    if st.button(
                        "💾 Salva ruolo",
                        key=f"role_btn_{user_id}",
                        use_container_width=True
                    ):

                        # Evita che l'amministratore corrente si tolga
                        # da solo i privilegi amministrativi.
                        if (
                            username == st.session_state.username
                            and nuovo_ruolo != "amministratore"
                        ):
                            st.warning(
                                "Non puoi rimuovere il tuo stesso ruolo amministratore."
                            )

                        else:

                            try:

                                (
                                    supabase
                                    .table("utenti")
                                    .update({
                                        "ruolo": nuovo_ruolo
                                    })
                                    .eq("id", user_id)
                                    .execute()
                                )

                                st.success("✅ Ruolo aggiornato!")

                                if username == st.session_state.username:
                                    st.session_state.ruolo = nuovo_ruolo

                                st.rerun()

                            except Exception as e:
                                st.error(f"Errore aggiornamento ruolo: {e}")

                # ------------------------------------------------
                # ATTIVA / DISATTIVA ACCOUNT
                # ------------------------------------------------

                with col3:

                    st.write("### 🚫 Account")

                    if username == st.session_state.username:

                        st.info("Non puoi disattivare il tuo account.")

                    else:

                        if attivo:

                            if st.button(
                                "🚫 Disattiva",
                                key=f"disable_{user_id}",
                                use_container_width=True
                            ):

                                try:

                                    (
                                        supabase
                                        .table("utenti")
                                        .update({"attivo": False})
                                        .eq("id", user_id)
                                        .execute()
                                    )

                                    st.warning("Account disattivato.")
                                    st.rerun()

                                except Exception as e:
                                    st.error(f"Errore disattivazione account: {e}")

                        else:

                            if st.button(
                                "✅ Riattiva",
                                key=f"enable_{user_id}",
                                use_container_width=True
                            ):

                                try:

                                    (
                                        supabase
                                        .table("utenti")
                                        .update({"attivo": True})
                                        .eq("id", user_id)
                                        .execute()
                                    )

                                    st.success("Account riattivato.")
                                    st.rerun()

                                except Exception as e:
                                    st.error(f"Errore riattivazione account: {e}")

    except Exception as e:
        st.error(f"Errore caricamento utenti: {e}")


# ============================================================
# GESTIONE CATEGORIE AMMINISTRATORE
# ============================================================

def sezione_gestione_categorie():

    st.subheader("🏷️ Gestione Categorie")

    st.info(
        "Le categorie disattivate non saranno disponibili nei nuovi ticket, "
        "ma resteranno visibili nello storico dei ticket già creati."
    )

    with st.expander("➕ Aggiungi nuova categoria", expanded=False):

        with st.form("form_aggiungi_categoria"):

            nuova_categoria = st.text_input(
                "Nome nuova categoria",
                placeholder="Esempio: Porte e serrature"
            )

            aggiungi = st.form_submit_button(
                "➕ Aggiungi categoria",
                use_container_width=True
            )

        if aggiungi:

            successo, messaggio = aggiungi_categoria(nuova_categoria)

            if successo:
                st.success(f"✅ {messaggio}")
                st.rerun()
            else:
                st.error(f"❌ {messaggio}")

    st.divider()
    st.subheader("📋 Categorie registrate")

    categorie = get_categorie(solo_attive=False)

    if not categorie:
        st.warning("Nessuna categoria disponibile.")
        return

    for categoria in categorie:

        categoria_id = categoria.get("id")
        nome = categoria.get("nome", "")
        attivo = categoria.get("attivo", True)

        stato = "🟢 Attiva" if attivo else "🔴 Disattivata"

        with st.expander(f"🏷️ {nome} | {stato}"):

            col1, col2 = st.columns(2)

            with col1:

                st.write("### ✏️ Modifica")

                nuovo_nome = st.text_input(
                    "Nome categoria",
                    value=nome,
                    key=f"categoria_nome_{categoria_id}"
                )

                st.caption(
                    "La modifica aggiornerà anche i ticket "
                    "che utilizzano questa categoria."
                )

                if st.button(
                    "💾 Salva modifica",
                    key=f"salva_categoria_{categoria_id}",
                    use_container_width=True
                ):

                    successo, messaggio = modifica_categoria(
                        categoria_id,
                        nome,
                        nuovo_nome
                    )

                    if successo:
                        st.success(f"✅ {messaggio}")
                        st.rerun()
                    else:
                        st.error(f"❌ {messaggio}")

            with col2:

                st.write("### 🚫 Stato")

                if attivo:

                    st.write(
                        "La categoria è disponibile per i nuovi ticket."
                    )

                    if st.button(
                        "🚫 Disattiva categoria",
                        key=f"disattiva_categoria_{categoria_id}",
                        use_container_width=True
                    ):

                        successo, messaggio = cambia_stato_categoria(
                            categoria_id,
                            False
                        )

                        if successo:
                            st.warning("Categoria disattivata.")
                            st.rerun()
                        else:
                            st.error(f"❌ {messaggio}")

                else:

                    st.write(
                        "La categoria non è disponibile nei nuovi ticket."
                    )

                    if st.button(
                        "✅ Riattiva categoria",
                        key=f"riattiva_categoria_{categoria_id}",
                        use_container_width=True
                    ):

                        successo, messaggio = cambia_stato_categoria(
                            categoria_id,
                            True
                        )

                        if successo:
                            st.success("Categoria riattivata.")
                            st.rerun()
                        else:
                            st.error(f"❌ {messaggio}")


# ============================================================
# AREA AMMINISTRATORE
# ============================================================

def pagina_amministrazione():

    if not is_admin():
        st.error("⛔ Accesso riservato all'amministratore.")
        return

    st.title("👨‍💼 Amministrazione")

    st.success(
        f"Accesso amministratore: {st.session_state.username}"
    )

    tab_utenti, tab_categorie = st.tabs([
        "👥 Gestione Utenti",
        "🏷️ Gestione Categorie"
    ])

    with tab_utenti:
        sezione_gestione_utenti()

    with tab_categorie:
        sezione_gestione_categorie()


# ============================================================
# MENU PRINCIPALE
# ============================================================

def applicazione():

    with st.sidebar:

        st.title("🎫 Gestione Ticket")

        st.write(
            f"👤 **{st.session_state.username}**"
        )

        st.caption(
            f"Ruolo: {st.session_state.ruolo}"
        )

        st.divider()

        if st.button(
            "🏠 Dashboard",
            use_container_width=True
        ):
            st.session_state.pagina = "Dashboard"

        if st.button(
            "➕ Nuovo Ticket",
            use_container_width=True
        ):
            st.session_state.pagina = "Nuovo Ticket"

        if st.button(
            "🎫 Ticket Gestiti",
            use_container_width=True
        ):
            st.session_state.pagina = "Ticket"

        if st.button(
            "📁 Archivio",
            use_container_width=True
        ):
            st.session_state.pagina = "Archivio"

        if st.button(
            "🔐 La mia Password",
            use_container_width=True
        ):
            st.session_state.pagina = "Password"

        if is_admin():

            if st.button(
                "👨‍💼 Amministrazione",
                use_container_width=True
            ):
                st.session_state.pagina = "Amministrazione"

        st.divider()

        if st.button(
            "🚪 Logout",
            use_container_width=True
        ):

            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.ruolo = ""
            st.session_state.pagina = "Dashboard"

            st.rerun()

    # --------------------------------------------------------
    # PAGINE
    # --------------------------------------------------------

    if st.session_state.pagina == "Dashboard":
        pagina_dashboard()

    elif st.session_state.pagina == "Nuovo Ticket":
        pagina_nuovo_ticket()

    elif st.session_state.pagina == "Ticket":
        pagina_ticket()

    elif st.session_state.pagina == "Archivio":
        pagina_archivio()

    elif st.session_state.pagina == "Password":
        pagina_password()

    elif st.session_state.pagina == "Amministrazione":
        pagina_amministrazione()


# ============================================================
# AVVIO
# ============================================================

if not st.session_state.logged_in:

    pagina_login()

else:

    applicazione()
