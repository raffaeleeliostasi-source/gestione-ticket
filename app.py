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
    return st.session_state.get("ruolo", "") == "amministratore"


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

        if not username or not password:
            st.warning("Inserisci username e password.")
            return

        try:

            risposta = (
                supabase
                .table("utenti")
                .select("*")
                .eq("username", username)
                .eq("password", password)
                .execute()
            )

            if risposta.data:

                utente = risposta.data[0]

                st.session_state.logged_in = True
                st.session_state.username = utente["username"]
                st.session_state.ruolo = utente["ruolo"]

                st.success("Login effettuato!")

                st.rerun()

            else:
                st.error("❌ Username o password non corretti.")

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

            categoria = st.selectbox(
                "Categoria",
                [
                    "Generale",
                    "Tecnico",
                    "Software",
                    "Hardware",
                    "Rete",
                    "Altro"
                ]
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

            col_admin1, col_admin2 = st.columns(2)

            # CHIUSURA

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

            # PDF

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
        "I ticket chiusi sono archiviati e non possono più essere modificati."
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
# AREA AMMINISTRATORE
# ============================================================

def pagina_amministrazione():

    if not is_admin():

        st.error(
            "⛔ Accesso riservato all'amministratore."
        )

        return

    st.title("👨‍💼 Amministrazione")

    st.success(
        f"Accesso amministratore: {st.session_state.username}"
    )

    st.subheader("👥 Utenti")

    try:

        risposta = (
            supabase
            .table("utenti")
            .select("*")
            .execute()
        )

        utenti = risposta.data or []

        if utenti:

            st.dataframe(
                utenti,
                use_container_width=True
            )

        else:

            st.info("Nessun utente trovato.")

    except Exception as e:

        st.error(f"Errore caricamento utenti: {e}")


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

    elif st.session_state.pagina == "Amministrazione":

        pagina_amministrazione()


# ============================================================
# AVVIO
# ============================================================

if not st.session_state.logged_in:

    pagina_login()

else:

    applicazione()