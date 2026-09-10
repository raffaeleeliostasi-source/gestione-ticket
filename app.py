import streamlit as st
from streamlit_drawable_canvas import st_canvas
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


def get_tecnici_attivi():
    """Restituisce gli username dei tecnici attivi."""

    try:
        risposta = (
            supabase
            .table("utenti")
            .select("*")
            .order("username")
            .execute()
        )

        utenti = risposta.data or []

        tecnici = [
            utente.get("username", "")
            for utente in utenti
            if utente.get("username")
            and utente.get("attivo", True) is not False
            and str(utente.get("ruolo", "")).strip().lower() == "tecnico"
        ]

        return tecnici

    except Exception as e:
        st.error(f"Errore caricamento tecnici: {e}")
        return []


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
# INTERVENTO TECNICO
# ============================================================

def get_intervento(ticket_id):
    """Restituisce l'intervento tecnico associato al ticket."""

    try:
        risposta = (
            supabase
            .table("ticket_interventi")
            .select("*")
            .eq("ticket_id", ticket_id)
            .execute()
        )

        if risposta.data:
            return risposta.data[0]

        return None

    except Exception as e:
        st.error(f"Errore caricamento intervento tecnico: {e}")
        return None


def salva_intervento_tecnico(
    ticket_id,
    tecnico,
    descrizione_intervento,
    nuovo_stato,
    firma_path=None
):
    """
    Salva un unico intervento per ticket.
    Se esiste già un intervento in lavorazione, viene aggiornato.
    """

    try:
        dati = {
            "ticket_id": ticket_id,
            "tecnico": tecnico,
            "descrizione": descrizione_intervento.strip(),
            "stato": nuovo_stato,
            "data_intervento": datetime.now().isoformat(),
            "firma_path": firma_path
        }

        intervento_esistente = get_intervento(ticket_id)

        if intervento_esistente:

            (
                supabase
                .table("ticket_interventi")
                .update(dati)
                .eq("ticket_id", ticket_id)
                .execute()
            )

        else:

            (
                supabase
                .table("ticket_interventi")
                .insert(dati)
                .execute()
            )

        # Aggiorna contemporaneamente lo stato principale del ticket.
        (
            supabase
            .table("tickets")
            .update({
                "stato": nuovo_stato
            })
            .eq("id", ticket_id)
            .eq("assegnato_a", tecnico)
            .execute()
        )

        return True, "Intervento salvato correttamente."

    except Exception as e:
        return False, str(e)


# ============================================================
# FIRMA GRAFICA DEL TECNICO
# ============================================================

def salva_firma_intervento(ticket_id, firma_png, tecnico):
    """Salva la firma PNG del tecnico nello Storage Supabase."""

    try:
        nome_file = (
            f"firma_ticket_{ticket_id}_{tecnico}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )

        percorso = f"firme/{ticket_id}/{nome_file}"

        # Il bucket utilizzato è lo stesso degli allegati dell'app.
        supabase.storage.from_("allegati").upload(
            percorso,
            firma_png,
            {
                "content-type": "image/png",
                "upsert": "true"
            }
        )

        return True, percorso

    except Exception as e:
        return False, str(e)


def scarica_firma_intervento(percorso):
    """Scarica la firma dal Supabase Storage."""

    try:
        return (
            supabase
            .storage
            .from_("allegati")
            .download(percorso)
        )

    except Exception:
        return None


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

    # Messaggio mostrato dopo il salvataggio, quando la pagina viene
    # riportata automaticamente al modulo di creazione.
    ticket_creato_id = st.session_state.pop("ticket_creato_id", None)
    if ticket_creato_id is not None:
        st.success(
            f"🎉 Ticket #{ticket_creato_id} creato correttamente!"
        )
        st.info(
            "Il modulo è pronto per inserire un nuovo ticket."
        )
        st.balloons()

    # ========================================================
    # CATEGORIA
    # ========================================================
    # La categoria è fuori dal form: così Streamlit aggiorna
    # subito la pagina quando si sceglie "➕ Nuova categoria...".

    categorie_attive = get_nomi_categorie_attive()
    opzione_nuova_categoria = "➕ Nuova categoria..."

    if is_admin():
        opzioni_categoria = categorie_attive + [opzione_nuova_categoria]
    else:
        opzioni_categoria = categorie_attive

    # Se una nuova categoria è stata appena salvata, impostiamo
    # la selezione PRIMA di creare il widget Streamlit.
    categoria_da_selezionare = st.session_state.pop(
        "categoria_da_selezionare", None
    )

    if categoria_da_selezionare in opzioni_categoria:
        st.session_state["categoria_nuovo_ticket"] = categoria_da_selezionare

    if not opzioni_categoria:

        st.warning(
            "⚠️ Non sono disponibili categorie attive. "
            "Contatta l'amministratore."
        )

        categoria = None

    else:

        categoria = st.selectbox(
            "Categoria",
            opzioni_categoria,
            key="categoria_nuovo_ticket"
        )

        # ====================================================
        # NUOVA CATEGORIA - SOLO AMMINISTRATORE
        # ====================================================

        if is_admin() and categoria == opzione_nuova_categoria:

            st.info(
                "➕ Inserisci il nome della nuova categoria e premi "
                "il pulsante per salvarla."
            )

            nuova_categoria = st.text_input(
                "Nome nuova categoria",
                placeholder="Esempio: Porte e serrature",
                key="nome_nuova_categoria_ticket"
            )

            if st.button(
                "➕ Aggiungi nuova categoria",
                key="aggiungi_categoria_dal_ticket",
                use_container_width=True
            ):

                if not nuova_categoria.strip():

                    st.warning(
                        "Inserisci il nome della nuova categoria."
                    )

                else:

                    successo, messaggio = aggiungi_categoria(
                        nuova_categoria
                    )

                    if successo:

                        st.success(
                            f"✅ Categoria '{nuova_categoria.strip()}' aggiunta correttamente!"
                        )

                        # Non modifichiamo direttamente la chiave del selectbox
                        # dopo che il widget è stato creato: Streamlit lo vieta.
                        st.session_state[
                            "categoria_da_selezionare"
                        ] = nuova_categoria.strip()

                        st.rerun()

                    else:

                        categorie_aggiornate = get_nomi_categorie_attive()

                        if nuova_categoria.strip() in categorie_aggiornate:

                            st.session_state[
                                "categoria_da_selezionare"
                            ] = nuova_categoria.strip()

                            st.rerun()

                        else:

                            st.error(f"❌ {messaggio}")

    # ========================================================
    # FORM NUOVO TICKET
    # ========================================================

    tecnici_attivi = get_tecnici_attivi()

    with st.form("nuovo_ticket_form"):

        titolo = st.text_input("Titolo del problema")

        descrizione = st.text_area(
            "Descrizione",
            height=150
        )

        col1, col2 = st.columns(2)

        with col1:

            if categoria and categoria != opzione_nuova_categoria:

                st.text_input(
                    "Categoria selezionata",
                    value=categoria,
                    disabled=True
                )

            else:

                st.text_input(
                    "Categoria selezionata",
                    value="Seleziona o crea una categoria",
                    disabled=True
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

        # ====================================================
        # ASSEGNAZIONE TICKET
        # ====================================================

        if tecnici_attivi:

            assegnato_a = st.selectbox(
                "👷 Assegna a",
                tecnici_attivi,
                help="Seleziona il tecnico responsabile del ticket."
            )

        else:

            assegnato_a = None

            st.warning(
                "⚠️ Non ci sono tecnici attivi disponibili per l'assegnazione."
            )

        st.divider()

        st.subheader("📎 Allegati")

        st.write(
            "Puoi caricare un file dalla galleria oppure usare la fotocamera."
        )

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

    # ========================================================
    # CREAZIONE TICKET
    # ========================================================

    if invia:

        if not titolo.strip():
            st.warning("Inserisci il titolo del ticket.")
            return

        if not categoria or categoria == opzione_nuova_categoria:
            st.warning(
                "Seleziona una categoria esistente oppure aggiungi "
                "prima la nuova categoria."
            )
            return

        if not descrizione.strip():
            st.warning("Inserisci una descrizione.")
            return

        if not assegnato_a:
            st.warning(
                "Seleziona un tecnico a cui assegnare il ticket."
            )
            return

        try:

            dati_ticket = {
                "titolo": titolo,
                "descrizione": descrizione,
                "categoria": categoria,
                "priorita": priorita,
                "assegnato_a": assegnato_a,
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

            if allegati:

                for file in allegati:

                    salva_allegato(
                        ticket_id,
                        file
                    )

            if foto:

                salva_allegato(
                    ticket_id,
                    foto
                )

            # Dopo la creazione torniamo sempre alla schermata
            # "➕ Nuovo Ticket", pronta per inserire un altro ticket.
            st.session_state.pagina = "Nuovo Ticket"
            st.session_state.ticket_creato_id = ticket_id

            st.rerun()

        except Exception as e:

            st.error(
                f"❌ Errore durante la creazione del ticket: {e}"
            )

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

        # 4. Elimina l'intervento tecnico collegato
        (
            supabase
            .table("ticket_interventi")
            .delete()
            .eq("ticket_id", ticket_id)
            .execute()
        )

        # 5. Elimina il ticket
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
    stato_ticket = ticket.get("stato", "Aperto")
    chiuso = stato_ticket == "Chiuso"

    with st.expander(
        f"🎫 #{ticket_id} - {ticket['titolo']} | {stato_ticket}",
        expanded=False
    ):

        # ====================================================
        # DATI TICKET
        # ====================================================

        col1, col2, col3 = st.columns(3)

        with col1:
            st.write(f"**Categoria:** {ticket.get('categoria', '')}")

        with col2:
            st.write(f"**Priorità:** {ticket.get('priorita', '')}")

        with col3:
            st.write(f"**Stato:** {stato_ticket}")

        st.write(f"**Creato da:** {ticket.get('creato_da', '')}")

        if ticket.get("assegnato_a"):
            st.write(
                f"**👷 Tecnico assegnato:** "
                f"{ticket.get('assegnato_a', '')}"
            )

        st.write("### 📝 Problema segnalato")
        st.write(ticket.get("descrizione", ""))

        st.divider()

        # ====================================================
        # INTERVENTO TECNICO SALVATO
        # ====================================================

        intervento = get_intervento(ticket_id)

        st.subheader("🔧 Intervento tecnico")

        if intervento:

            st.success("Intervento tecnico registrato")

            col_int1, col_int2, col_int3 = st.columns(3)

            with col_int1:
                st.write(
                    f"**👷 Tecnico:** "
                    f"{intervento.get('tecnico', '')}"
                )

            with col_int2:
                st.write(
                    f"**📅 Data intervento:** "
                    f"{format_data(intervento.get('data_intervento'))}"
                )

            with col_int3:
                st.write(
                    f"**🔄 Stato:** "
                    f"{intervento.get('stato', '')}"
                )

            st.write("#### 📝 Cosa è stato fatto")
            st.write(intervento.get("descrizione", ""))

            firma_path = intervento.get("firma_path")

            if firma_path:

                firma_bytes = scarica_firma_intervento(firma_path)

                if firma_bytes:

                    st.write("#### ✍️ Firma del tecnico")
                    st.image(
                        firma_bytes,
                        width=350
                    )

        else:

            st.info("Nessun intervento tecnico ancora registrato.")

        # ====================================================
        # AREA OPERATIVA TECNICO
        # ====================================================

        utente_corrente = st.session_state.username
        tecnico_assegnato = ticket.get("assegnato_a", "")

        if (
            not is_admin()
            and tecnico_assegnato == utente_corrente
        ):

            if chiuso:

                st.warning(
                    "🔒 Il ticket è chiuso dall'amministratore "
                    "e non può più essere modificato."
                )

            elif stato_ticket == "Risolto":

                st.success(
                    "✅ Hai completato l'intervento. "
                    "Il ticket è in attesa della chiusura dell'amministratore."
                )

            else:

                st.divider()
                st.subheader("🛠️ Registra il tuo intervento")

                testo_precedente = ""

                if intervento:
                    testo_precedente = intervento.get(
                        "descrizione", ""
                    )

                descrizione_intervento = st.text_area(
                    "📝 Cosa hai fatto?",
                    value=testo_precedente,
                    height=180,
                    key=f"intervento_testo_{ticket_id}",
                    placeholder=(
                        "Descrivi in modo chiaro l'intervento effettuato..."
                    )
                )

                col_stato1, col_stato2 = st.columns(2)

                with col_stato1:

                    stati_tecnico = [
                        "In lavorazione",
                        "Risolto"
                    ]

                    indice_stato = 0

                    if intervento:
                        stato_intervento = intervento.get(
                            "stato", "In lavorazione"
                        )

                        if stato_intervento in stati_tecnico:
                            indice_stato = stati_tecnico.index(
                                stato_intervento
                            )

                    nuovo_stato = st.selectbox(
                        "🔄 Stato dopo l'intervento",
                        stati_tecnico,
                        index=indice_stato,
                        key=f"intervento_stato_{ticket_id}"
                    )

                with col_stato2:

                    foto_intervento = st.file_uploader(
                        "📷 Foto dell'intervento (opzionale)",
                        type=["jpg", "jpeg", "png"],
                        accept_multiple_files=True,
                        key=f"foto_intervento_{ticket_id}"
                    )

                foto_camera = st.camera_input(
                    "📸 Scatta una foto dell'intervento (opzionale)",
                    key=f"camera_intervento_{ticket_id}"
                )

                st.divider()

                st.subheader("✍️ Firma del tecnico")

                st.caption(
                    "Disegna la tua firma nello spazio sottostante. "
                    "La firma è obbligatoria quando imposti il ticket su Risolto."
                )

                firma_canvas = st_canvas(
                    fill_color="rgba(255, 255, 255, 0)",
                    stroke_width=2,
                    stroke_color="#000000",
                    background_color="#FFFFFF",
                    height=180,
                    width=500,
                    drawing_mode="freedraw",
                    return_image_data=True,
                    key=f"firma_canvas_{ticket_id}"
                )

                if st.button(
                    "💾 Salva intervento",
                    key=f"salva_intervento_{ticket_id}",
                    use_container_width=True
                ):

                    if not descrizione_intervento.strip():

                        st.warning(
                            "Descrivi prima cosa hai fatto durante l'intervento."
                        )

                    else:

                        firma_png = None
                        firma_path = None

                        # Verifica se il tecnico ha effettivamente
                        # disegnato una firma.
                        canvas_json = firma_canvas.json_data

                        if (
                            canvas_json is not None
                            and canvas_json.get("objects")
                        ):

                            # Nelle versioni recenti della libreria i dati
                            # immagine sono opt-in. return_image_data=True
                            # abilita image_bytes direttamente in formato PNG.
                            firma_png = getattr(
                                firma_canvas,
                                "image_bytes",
                                None
                            )

                            # Fallback compatibile con eventuali versioni
                            # che espongono solo image_data.
                            if firma_png is None:

                                canvas_image = getattr(
                                    firma_canvas,
                                    "image_data",
                                    None
                                )

                                if canvas_image is not None:

                                    from PIL import Image

                                    firma_immagine = Image.fromarray(
                                        canvas_image.astype("uint8")
                                    )

                                    buffer_firma = BytesIO()

                                    firma_immagine.save(
                                        buffer_firma,
                                        format="PNG"
                                    )

                                    firma_png = buffer_firma.getvalue()

                        # La firma è obbligatoria solo per la risoluzione finale.
                        if nuovo_stato == "Risolto" and not firma_png:

                            st.warning(
                                "✍️ Per impostare il ticket su Risolto "
                                "devi inserire la firma del tecnico."
                            )
                            return

                        if firma_png:

                            esito_firma, risultato_firma = (
                                salva_firma_intervento(
                                    ticket_id,
                                    firma_png,
                                    utente_corrente
                                )
                            )

                            if not esito_firma:

                                st.error(
                                    f"❌ Errore salvataggio firma: "
                                    f"{risultato_firma}"
                                )
                                return

                            firma_path = risultato_firma

                        # Se non viene ridisegnata una firma durante un
                        # aggiornamento in lavorazione, conserva quella esistente.
                        elif intervento and intervento.get("firma_path"):

                            firma_path = intervento.get("firma_path")

                        successo, messaggio = salva_intervento_tecnico(
                            ticket_id,
                            utente_corrente,
                            descrizione_intervento,
                            nuovo_stato,
                            firma_path
                        )

                        if successo:

                            # Salva le eventuali foto insieme al ticket.
                            if foto_intervento:

                                for foto in foto_intervento:
                                    salva_allegato(ticket_id, foto)

                            if foto_camera:
                                salva_allegato(
                                    ticket_id,
                                    foto_camera
                                )

                            st.success(
                                "✅ Intervento salvato correttamente!"
                            )

                            st.rerun()

                        else:

                            st.error(
                                f"❌ Errore salvataggio intervento: {messaggio}"
                            )

        st.divider()

        # ====================================================
        # ALLEGATI E FOTO
        # ====================================================

        st.subheader("📎 Allegati e foto")

        allegati = get_allegati(ticket_id)

        if allegati:

            for allegato in allegati:

                nome_file = allegato.get("nome_file", "")
                tipo_file = allegato.get("tipo_file", "")
                percorso_file = allegato.get("percorso_file", "")

                if tipo_file.startswith("image/") and percorso_file:

                    contenuto = scarica_allegato(percorso_file)

                    if contenuto:
                        st.image(
                            contenuto,
                            caption=nome_file,
                            use_container_width=True
                        )
                    else:
                        st.write(f"📄 **{nome_file}**")

                else:

                    st.write(f"📄 **{nome_file}**")
                    st.caption(tipo_file)

        else:

            st.info("Nessun allegato.")

        st.divider()

        # ====================================================
        # AZIONI AMMINISTRATORE
        # ====================================================

        if is_admin():

            col_admin1, col_admin2, col_admin3 = st.columns(3)

            # ------------------------------------------------
            # CHIUSURA: possibile solo dopo RISOLTO
            # ------------------------------------------------

            with col_admin1:

                if chiuso:

                    st.success("📁 Ticket chiuso")

                elif stato_ticket != "Risolto":

                    st.info(
                        "🔒 Il ticket può essere chiuso solo dopo "
                        "che il tecnico lo ha impostato su Risolto."
                    )

                    st.button(
                        "🔒 Chiudi Ticket",
                        key=f"close_{ticket_id}",
                        use_container_width=True,
                        disabled=True
                    )

                else:

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
                                "🔒 Ticket chiuso dall'amministratore!"
                            )

                            st.rerun()

                        except Exception as e:

                            st.error(
                                f"Errore chiusura ticket: {e}"
                            )

            # ------------------------------------------------
            # PDF
            # ------------------------------------------------

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

            # ------------------------------------------------
            # ELIMINAZIONE
            # ------------------------------------------------

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
                        "l'intervento e tutti gli allegati."
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
                                    f"❌ Errore: {messaggio}"
                                )


# ============================================================
# GENERAZIONE PDF
# ============================================================

def genera_pdf(ticket):

    buffer = BytesIO()

    # ========================================================
    # STILI PDF
    # ========================================================

    styles = getSampleStyleSheet()

    stile_titolo = styles["Title"].clone("TicketTitle")
    stile_titolo.fontName = "Helvetica-Bold"
    stile_titolo.fontSize = 20
    stile_titolo.leading = 24
    stile_titolo.spaceAfter = 4

    stile_sottotitolo = styles["Normal"].clone("TicketSubtitle")
    stile_sottotitolo.fontName = "Helvetica"
    stile_sottotitolo.fontSize = 9
    stile_sottotitolo.textColor = colors.grey
    stile_sottotitolo.spaceAfter = 12

    stile_sezione = styles["Heading2"].clone("TicketSection")
    stile_sezione.fontName = "Helvetica-Bold"
    stile_sezione.fontSize = 13
    stile_sezione.leading = 16
    stile_sezione.spaceBefore = 10
    stile_sezione.spaceAfter = 8

    stile_testo = styles["BodyText"].clone("TicketBody")
    stile_testo.fontName = "Helvetica"
    stile_testo.fontSize = 9.5
    stile_testo.leading = 14
    stile_testo.spaceAfter = 6

    def testo_pdf(valore):
        """Converte il testo in una forma sicura per ReportLab."""
        if valore is None:
            return "-"
        valore = str(valore).strip()
        if not valore:
            return "-"
        return (valore.replace("&", "&amp;")
                      .replace("<", "&lt;")
                      .replace(">", "&gt;")
                      .replace("\n", "<br/>"))

    def intestazione_pagina(canvas, doc):
        canvas.saveState()
        larghezza, altezza = A4

        canvas.setStrokeColor(colors.HexColor("#D9D9D9"))
        canvas.line(40, altezza - 42, larghezza - 40, altezza - 42)

        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(40, altezza - 32, "GESTIONE TICKET")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            larghezza - 40,
            altezza - 32,
            f"Ticket #{ticket.get('id', '')}"
        )

        canvas.line(40, 35, larghezza - 40, 35)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(40, 23, "Report generato automaticamente da Gestione Ticket")
        canvas.drawRightString(larghezza - 40, 23, f"Pagina {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=58,
        bottomMargin=48
    )

    elementi = []

    # ========================================================
    # INTESTAZIONE TICKET
    # ========================================================

    elementi.append(
        Paragraph(
            f"Ticket #{testo_pdf(ticket.get('id', ''))}",
            stile_titolo
        )
    )
    elementi.append(
        Paragraph(
            testo_pdf(ticket.get("titolo", "Senza titolo")),
            stile_sottotitolo
        )
    )

    # ========================================================
    # RIEPILOGO
    # ========================================================

    elementi.append(Paragraph("Riepilogo ticket", stile_sezione))

    dati = [
        ["Categoria", testo_pdf(ticket.get("categoria", ""))],
        ["Priorità", testo_pdf(ticket.get("priorita", ""))],
        ["Stato", testo_pdf(ticket.get("stato", ""))],
        ["Creato da", testo_pdf(ticket.get("creato_da", ""))],
        ["Assegnato a", testo_pdf(ticket.get("assegnato_a", ""))]
    ]

    tabella = Table(
        dati,
        colWidths=[125, 365],
        repeatRows=0
    )

    tabella.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F3F5")),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#333333")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D4D8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
        ])
    )

    elementi.append(tabella)

    # ========================================================
    # PROBLEMA SEGNALATO
    # ========================================================

    elementi.append(Paragraph("Problema segnalato", stile_sezione))
    elementi.append(
        Paragraph(
            testo_pdf(ticket.get("descrizione", "")),
            stile_testo
        )
    )

    # ========================================================
    # INTERVENTO TECNICO
    # ========================================================

    intervento = get_intervento(ticket["id"])

    if intervento:

        elementi.append(Paragraph("Intervento tecnico", stile_sezione))

        dati_intervento = [
            ["Tecnico", testo_pdf(intervento.get("tecnico", ""))],
            [
                "Data intervento",
                testo_pdf(format_data(intervento.get("data_intervento")))
            ],
            ["Esito", testo_pdf(intervento.get("stato", ""))]
        ]

        tabella_intervento = Table(
            dati_intervento,
            colWidths=[125, 365]
        )
        tabella_intervento.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F3F5")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D4D8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
            ])
        )
        elementi.append(tabella_intervento)
        elementi.append(Spacer(1, 10))

        elementi.append(
            Paragraph(
                "Descrizione dell'intervento",
                styles["Heading3"]
            )
        )
        elementi.append(
            Paragraph(
                testo_pdf(intervento.get("descrizione", "")),
                stile_testo
            )
        )

        # ====================================================
        # FIRMA TECNICO
        # ====================================================

        firma_path = intervento.get("firma_path")

        if firma_path:
            firma_bytes = scarica_firma_intervento(firma_path)

            if firma_bytes:
                try:
                    elementi.append(Spacer(1, 10))
                    elementi.append(
                        Paragraph(
                            "Firma del tecnico",
                            styles["Heading3"]
                        )
                    )

                    firma_reader = ImageReader(BytesIO(firma_bytes))
                    larghezza, altezza = firma_reader.getSize()
                    max_larghezza = 250
                    max_altezza = 90
                    rapporto = min(
                        max_larghezza / larghezza,
                        max_altezza / altezza,
                        1
                    )

                    elementi.append(
                        RLImage(
                            BytesIO(firma_bytes),
                            width=larghezza * rapporto,
                            height=altezza * rapporto
                        )
                    )
                    elementi.append(Spacer(1, 5))
                    elementi.append(
                        Paragraph(
                            testo_pdf(intervento.get("tecnico", "")),
                            stile_sottotitolo
                        )
                    )

                except Exception:
                    elementi.append(
                        Paragraph(
                            "Firma del tecnico non disponibile nel PDF.",
                            stile_testo
                        )
                    )

    # ========================================================
    # FOTO E ALLEGATI
    # ========================================================

    allegati = get_allegati(ticket["id"])
    immagini_aggiunte = False
    numero_allegati = len(allegati)

    if numero_allegati:
        elementi.append(Paragraph("Allegati", stile_sezione))
        elementi.append(
            Paragraph(
                f"Numero allegati: {numero_allegati}",
                stile_sottotitolo
            )
        )

    for allegato in allegati:

        tipo_file = allegato.get("tipo_file", "")
        nome_file = allegato.get("nome_file", "")
        percorso_file = allegato.get("percorso_file", "")

        if tipo_file.startswith("image/") and percorso_file:

            contenuto = scarica_allegato(percorso_file)

            if contenuto:

                if not immagini_aggiunte:
                    elementi.append(
                        Paragraph(
                            "Documentazione fotografica",
                            styles["Heading3"]
                        )
                    )
                    immagini_aggiunte = True

                try:
                    immagine_buffer = BytesIO(contenuto)
                    image_reader = ImageReader(immagine_buffer)
                    larghezza, altezza = image_reader.getSize()

                    max_larghezza = 490
                    max_altezza = 520
                    rapporto = min(
                        max_larghezza / larghezza,
                        max_altezza / altezza,
                        1
                    )

                    elementi.append(
                        Paragraph(
                            testo_pdf(nome_file),
                            stile_sottotitolo
                        )
                    )
                    elementi.append(
                        RLImage(
                            BytesIO(contenuto),
                            width=larghezza * rapporto,
                            height=altezza * rapporto
                        )
                    )
                    elementi.append(Spacer(1, 12))

                except Exception:
                    elementi.append(
                        Paragraph(
                            f"Impossibile inserire l'immagine {testo_pdf(nome_file)}.",
                            stile_testo
                        )
                    )

    # ========================================================
    # GENERAZIONE
    # ========================================================

    doc.build(
        elementi,
        onFirstPage=intestazione_pagina,
        onLaterPages=intestazione_pagina
    )

    buffer.seek(0)

    return buffer.getvalue()


# ============================================================
# DASHBOARD
# ============================================================

def pagina_dashboard():

    st.title("🏠 Dashboard")
    st.caption("Centro di controllo della gestione ticket")

    tickets = get_tickets()

    if not tickets:
        st.info("Non ci sono ancora ticket.")
        return

    # ========================================================
    # KPI PRINCIPALI
    # ========================================================

    aperti = sum(1 for t in tickets if t.get("stato") == "Aperto")
    lavorazione = sum(
        1 for t in tickets
        if t.get("stato") == "In lavorazione"
    )
    risolti = sum(1 for t in tickets if t.get("stato") == "Risolto")
    chiusi = sum(1 for t in tickets if t.get("stato") == "Chiuso")
    urgenti = sum(1 for t in tickets if t.get("priorita") == "Urgente")

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("🎫 Totali", len(tickets))
    col2.metric("🟢 Aperti", aperti)
    col3.metric("🟠 In lavorazione", lavorazione)
    col4.metric("🔵 Risolti", risolti)
    col5.metric("🔴 Urgenti", urgenti)

    st.divider()

    # ========================================================
    # FILTRI
    # ========================================================

    st.subheader("🔎 Filtra ticket")

    col1, col2, col3 = st.columns(3)

    testo = col1.text_input(
        "Cerca",
        placeholder="Titolo o descrizione...",
        key="dashboard_cerca"
    )

    stati = ["Tutti"] + sorted({
        str(t.get("stato", ""))
        for t in tickets
        if t.get("stato")
    })
    filtro_stato = col2.selectbox(
        "Stato",
        stati,
        key="dashboard_stato"
    )

    priorita_opzioni = ["Tutte"] + sorted({
        str(t.get("priorita", ""))
        for t in tickets
        if t.get("priorita")
    })
    filtro_priorita = col3.selectbox(
        "Priorità",
        priorita_opzioni,
        key="dashboard_priorita"
    )

    col4, col5 = st.columns(2)

    tecnici = sorted({
        str(t.get("assegnato_a", ""))
        for t in tickets
        if t.get("assegnato_a")
    })
    filtro_tecnico = col4.selectbox(
        "👷 Tecnico",
        ["Tutti"] + tecnici,
        key="dashboard_tecnico"
    )

    categorie = sorted({
        str(t.get("categoria", ""))
        for t in tickets
        if t.get("categoria")
    })
    filtro_categoria = col5.selectbox(
        "🏷️ Categoria",
        ["Tutte"] + categorie,
        key="dashboard_categoria"
    )

    # ========================================================
    # APPLICA FILTRI
    # ========================================================

    tickets_filtrati = []

    testo_lower = testo.strip().lower()

    for ticket in tickets:
        titolo = str(ticket.get("titolo", ""))
        descrizione = str(ticket.get("descrizione", ""))

        if testo_lower and testo_lower not in (
            titolo + " " + descrizione
        ).lower():
            continue

        if filtro_stato != "Tutti" and ticket.get("stato") != filtro_stato:
            continue

        if (
            filtro_priorita != "Tutte"
            and ticket.get("priorita") != filtro_priorita
        ):
            continue

        if (
            filtro_tecnico != "Tutti"
            and ticket.get("assegnato_a") != filtro_tecnico
        ):
            continue

        if (
            filtro_categoria != "Tutte"
            and ticket.get("categoria") != filtro_categoria
        ):
            continue

        tickets_filtrati.append(ticket)

    st.write(
        f"**{len(tickets_filtrati)}** ticket corrispondenti ai filtri selezionati."
    )

    st.divider()

    # ========================================================
    # STATISTICHE
    # ========================================================

    st.subheader("📊 Panoramica")

    col1, col2 = st.columns(2)

    stati_dashboard = {}
    for ticket in tickets_filtrati:
        stato = ticket.get("stato") or "Senza stato"
        stati_dashboard[stato] = stati_dashboard.get(stato, 0) + 1

    categorie_dashboard = {}
    for ticket in tickets_filtrati:
        categoria = ticket.get("categoria") or "Senza categoria"
        categorie_dashboard[categoria] = (
            categorie_dashboard.get(categoria, 0) + 1
        )

    with col1:
        st.markdown("**📌 Ticket per stato**")
        if stati_dashboard:
            st.bar_chart(stati_dashboard)
        else:
            st.info("Nessun dato disponibile.")

    with col2:
        st.markdown("**🏷️ Ticket per categoria**")
        if categorie_dashboard:
            st.bar_chart(categorie_dashboard)
        else:
            st.info("Nessun dato disponibile.")

    st.markdown("**👷 Ticket per tecnico**")

    tecnici_dashboard = {}
    for ticket in tickets_filtrati:
        tecnico = ticket.get("assegnato_a") or "Non assegnato"
        tecnici_dashboard[tecnico] = tecnici_dashboard.get(tecnico, 0) + 1

    if tecnici_dashboard:
        st.bar_chart(tecnici_dashboard)
    else:
        st.info("Nessun dato disponibile.")

    st.divider()

    # ========================================================
    # TICKET RECENTI
    # ========================================================

    st.subheader("🎫 Ticket recenti")

    recenti = tickets_filtrati[:5]

    if recenti:
        for ticket in recenti:
            mostra_ticket(ticket)
    else:
        st.info("Nessun ticket corrisponde ai filtri selezionati.")


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
