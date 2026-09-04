import io
import sqlite3
import hashlib
import hmac
import secrets
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

# Google Drive
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import (
        MediaIoBaseUpload,
        MediaIoBaseDownload,
    )
    GOOGLE_LIBRARIES_AVAILABLE = True
except ImportError:
    GOOGLE_LIBRARIES_AVAILABLE = False


# ============================================================
# CONFIGURAZIONE PAGINA
# ============================================================

st.set_page_config(
    page_title="Gestione Ticket",
    page_icon="🎫",
    layout="wide",
)

DB_NAME = "ticket.db"

STATI = [
    "Aperto",
    "In Corso",
    "Risolto",
    "Chiuso",
]

PRIORITA = [
    "Bassa",
    "Media",
    "Alta",
    "Critica",
]

RUOLI = [
    "Amministratore",
    "Tecnico",
]

# Se conosci l'ID di una cartella Drive principale,
# puoi inserirlo qui.
#
# Se rimane vuoto, l'app cercherà di creare:
#
# Gestione Ticket
# ├── Da gestire
# │   ├── tecnico1
# │   └── ...
# └── Gestiti
#     ├── tecnico1
#     └── ...
#
DRIVE_ROOT_FOLDER_ID = "1wZrLqf518oh7Rp43bIToiw_779J8BtPj"


# ============================================================
# PASSWORD
# ============================================================

def make_hash(password):
    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,
    )

    return salt.hex() + "$" + password_hash.hex()


def check_hash(password, stored_password):
    try:
        salt_hex, hash_hex = stored_password.split("$")

        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            200_000,
        )

        return hmac.compare_digest(
            password_hash,
            expected_hash,
        )

    except (ValueError, TypeError):
        return False


# ============================================================
# DATABASE
# ============================================================

@st.cache_resource
def get_connection():
    return sqlite3.connect(
        DB_NAME,
        check_same_thread=False,
    )


conn = get_connection()


def execute(
    query,
    params=(),
    fetchone=False,
    fetchall=False,
):
    cursor = conn.cursor()

    try:
        cursor.execute(query, params)

        if fetchone:
            return cursor.fetchone()

        if fetchall:
            return cursor.fetchall()

        conn.commit()

    finally:
        cursor.close()


def init_database():

    execute(
        """
        CREATE TABLE IF NOT EXISTS utenti (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            ruolo TEXT NOT NULL
        )
        """
    )

    execute(
        """
        CREATE TABLE IF NOT EXISTS ticket (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            ambiente TEXT NOT NULL,
            descrizione TEXT NOT NULL,
            priorita TEXT NOT NULL,
            assegnato_a TEXT NOT NULL,
            creato_da TEXT NOT NULL,
            stato TEXT NOT NULL,
            note_tecnico TEXT DEFAULT '',
            creato_il TEXT NOT NULL,
            modificato_il TEXT NOT NULL
        )
        """
    )

    execute(
        """
        CREATE TABLE IF NOT EXISTS ticket_file_version (
            username TEXT PRIMARY KEY,
            versione INTEGER NOT NULL DEFAULT 1,
            generato_il TEXT NOT NULL,
            file_name TEXT NOT NULL
        )
        """
    )

    execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ticket_stato
        ON ticket(stato)
        """
    )

    execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ticket_priorita
        ON ticket(priorita)
        """
    )

    execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ticket_assegnato
        ON ticket(assegnato_a)
        """
    )


init_database()

# ============================================================
# UTENTI DEFAULT
# ============================================================

def create_default_users():

    count = execute(
        "SELECT COUNT(*) FROM utenti",
        fetchone=True,
    )[0]

    if count > 0:
        return

    execute(
        """
        INSERT INTO utenti
        (username, password, ruolo)
        VALUES (?, ?, ?)
        """,
        (
            "admin",
            make_hash("admin123"),
            "Amministratore",
        ),
    )

    execute(
        """
        INSERT INTO utenti
        (username, password, ruolo)
        VALUES (?, ?, ?)
        """,
        (
            "tecnico1",
            make_hash("pass123"),
            "Tecnico",
        ),
    )


create_default_users()


# ============================================================
# SESSIONE
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "ruolo" not in st.session_state:
    st.session_state.ruolo = ""


def is_admin():
    return (
        st.session_state.ruolo
        == "Amministratore"
    )


def logout():

    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.ruolo = ""

    st.rerun()


# ============================================================
# GOOGLE DRIVE
# ============================================================

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive"
]


@st.cache_resource
def get_drive_service():

    if not GOOGLE_LIBRARIES_AVAILABLE:
        return None

    if "google_service_account" not in st.secrets:
        return None

    credentials = (
        service_account
        .Credentials
        .from_service_account_info(
            st.secrets[
                "google_service_account"
            ],
            scopes=DRIVE_SCOPES,
        )
    )

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def drive_available():

    try:
        return get_drive_service() is not None
    except Exception:
        return False


def find_drive_folder(
    service,
    name,
    parent_id=None,
):

    escaped_name = name.replace(
        "'",
        "\\'",
    )

    query = (
        "mimeType = "
        "'application/vnd.google-apps.folder' "
        f"and name = '{escaped_name}' "
        "and trashed = false"
    )

    if parent_id:
        query += (
            f" and '{parent_id}' in parents"
        )

    result = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id,name)",
        pageSize=100,
    ).execute()

    files = result.get(
        "files",
        [],
    )

    if files:
        return files[0]["id"]

    return None


def create_drive_folder(
    service,
    name,
    parent_id=None,
):

    metadata = {
        "name": name,
        "mimeType": (
            "application/vnd.google-apps.folder"
        ),
    }

    if parent_id:
        metadata["parents"] = [
            parent_id
        ]

    folder = service.files().create(
        body=metadata,
        fields="id",
    ).execute()

    return folder["id"]


def get_or_create_folder(
    service,
    name,
    parent_id=None,
):

    folder_id = find_drive_folder(
        service,
        name,
        parent_id,
    )

    if folder_id:
        return folder_id

    return create_drive_folder(
        service,
        name,
        parent_id,
    )


def get_drive_structure():

    service = get_drive_service()

    if not service:
        return None

    root_id = DRIVE_ROOT_FOLDER_ID

    if not root_id:

        root_id = get_or_create_folder(
            service,
            "Gestione Ticket",
        )

    da_gestire_id = get_or_create_folder(
        service,
        "Da gestire",
        root_id,
    )

    gestiti_id = get_or_create_folder(
        service,
        "Gestiti",
        root_id,
    )

    return {
        "root": root_id,
        "da_gestire": da_gestire_id,
        "gestiti": gestiti_id,
    }


def get_technician_drive_folders(
    username
):

    structure = get_drive_structure()

    if not structure:
        return None

    da_gestire = (
        get_or_create_folder(
            get_drive_service(),
            username,
            structure["da_gestire"],
        )
    )

    gestiti = (
        get_or_create_folder(
            get_drive_service(),
            username,
            structure["gestiti"],
        )
    )

    return {
        "da_gestire": da_gestire,
        "gestiti": gestiti,
    }


def find_drive_file(
    service,
    filename,
    folder_id,
):

    escaped_name = filename.replace(
        "'",
        "\\'",
    )

    query = (
        f"name = '{escaped_name}' "
        f"and '{folder_id}' in parents "
        "and trashed = false"
    )

    result = service.files().list(
        q=query,
        spaces="drive",
        fields=(
            "files("
            "id,"
            "name,"
            "parents,"
            "modifiedTime,"
            "webViewLink"
            ")"
        ),
        pageSize=100,
    ).execute()

    files = result.get(
        "files",
        [],
    )

    return files[0] if files else None


def upload_or_update_drive_file(
    file_bytes,
    filename,
    folder_id,
):

    service = get_drive_service()

    existing = find_drive_file(
        service,
        filename,
        folder_id,
    )

    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes),
        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
        resumable=False,
    )

    if existing:

        return service.files().update(
            fileId=existing["id"],
            media_body=media,
            fields=(
                "id,"
                "name,"
                "parents,"
                "modifiedTime,"
                "webViewLink"
            ),
        ).execute()

    metadata = {
        "name": filename,
        "parents": [folder_id],
    }

    return service.files().create(
        body=metadata,
        media_body=media,
        fields=(
            "id,"
            "name,"
            "parents,"
            "modifiedTime,"
            "webViewLink"
        ),
    ).execute()


def upload_file_to_drive(
    file_bytes,
    filename,
    folder_id,
):

    service = get_drive_service()

    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes),
        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
        resumable=False,
    )

    metadata = {
        "name": filename,
        "parents": [folder_id],
    }

    return service.files().create(
        body=metadata,
        media_body=media,
        fields=(
            "id,"
            "name,"
            "parents,"
            "modifiedTime,"
            "webViewLink"
        ),
    ).execute()


def move_drive_file(
    file_id,
    destination_folder_id,
):

    service = get_drive_service()

    file_info = service.files().get(
        fileId=file_id,
        fields="parents",
    ).execute()

    previous_parents = ",".join(
        file_info.get(
            "parents",
            [],
        )
    )

    return service.files().update(
        fileId=file_id,
        addParents=destination_folder_id,
        removeParents=previous_parents,
        fields=(
            "id,"
            "name,"
            "parents,"
            "modifiedTime"
        ),
    ).execute()


def list_drive_files(
    folder_id
):

    service = get_drive_service()

    result = service.files().list(
        q=(
            f"'{folder_id}' in parents "
            "and trashed = false"
        ),
        spaces="drive",
        fields=(
            "files("
            "id,"
            "name,"
            "mimeType,"
            "modifiedTime,"
            "webViewLink"
            ")"
        ),
        orderBy="modifiedTime desc",
        pageSize=100,
    ).execute()

    return result.get(
        "files",
        [],
    )


def download_drive_file(
    file_id
):

    service = get_drive_service()

    request = service.files().get_media(
        fileId=file_id
    )

    buffer = io.BytesIO()

    downloader = MediaIoBaseDownload(
        buffer,
        request,
    )

    done = False

    while not done:

        _, done = (
            downloader.next_chunk()
        )

    buffer.seek(0)

    return buffer.read()


# ============================================================
# VERSIONAMENTO FILE
# ============================================================

def get_file_version(username):

    result = execute(
        """
        SELECT versione
        FROM ticket_file_version
        WHERE username = ?
        """,
        (username,),
        fetchone=True,
    )

    if result:
        return result[0]

    return 0


def create_file_version(
    username,
    filename,
):

    current = get_file_version(
        username
    )

    new_version = current + 1

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    execute(
        """
        INSERT INTO ticket_file_version
        (
            username,
            versione,
            generato_il,
            file_name
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(username)
        DO UPDATE SET
            versione = excluded.versione,
            generato_il = excluded.generato_il,
            file_name = excluded.file_name
        """,
        (
            username,
            new_version,
            now,
            filename,
        ),
    )

    return new_version


def get_file_info(username):

    return execute(
        """
        SELECT
            username,
            versione,
            generato_il,
            file_name
        FROM ticket_file_version
        WHERE username = ?
        """,
        (username,),
        fetchone=True,
    )


# ============================================================
# QUERY TICKET
# ============================================================

def get_tickets():

    return pd.read_sql_query(
        """
        SELECT
            id,
            data,
            ambiente,
            descrizione,
            priorita,
            assegnato_a,
            creato_da,
            stato,
            note_tecnico,
            creato_il,
            modificato_il
        FROM ticket
        ORDER BY id DESC
        """,
        conn,
    )


def get_technician_tickets(
    username
):

    return pd.read_sql_query(
        """
        SELECT
            id,
            data,
            ambiente,
            descrizione,
            priorita,
            stato,
            note_tecnico,
            assegnato_a
        FROM ticket
        WHERE assegnato_a = ?
        ORDER BY id DESC
        """,
        conn,
        params=(username,),
    )


def get_users():

    return execute(
        """
        SELECT username, ruolo
        FROM utenti
        ORDER BY username
        """,
        fetchall=True,
    )


# ============================================================
# CREAZIONE TICKET
# ============================================================

def create_ticket(
    data,
    ambiente,
    descrizione,
    priorita,
    assegnato_a,
    creato_da,
):

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    execute(
        """
        INSERT INTO ticket
        (
            data,
            ambiente,
            descrizione,
            priorita,
            assegnato_a,
            creato_da,
            stato,
            note_tecnico,
            creato_il,
            modificato_il
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data,
            ambiente.strip(),
            descrizione.strip(),
            priorita,
            assegnato_a,
            creato_da,
            "Aperto",
            "",
            now,
            now,
        ),
    )

    refresh_technician_drive_file(
        assegnato_a
    )


# ============================================================
# AGGIORNAMENTO ADMIN
# ============================================================

def update_ticket_admin(
    ticket_id,
    data,
    ambiente,
    descrizione,
    priorita,
    assegnato_a,
    stato,
    note_tecnico,
):

    old_ticket = execute(
        """
        SELECT assegnato_a
        FROM ticket
        WHERE id = ?
        """,
        (ticket_id,),
        fetchone=True,
    )

    old_assigned_to = (
        old_ticket[0]
        if old_ticket
        else None
    )

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    execute(
        """
        UPDATE ticket
        SET
            data = ?,
            ambiente = ?,
            descrizione = ?,
            priorita = ?,
            assegnato_a = ?,
            stato = ?,
            note_tecnico = ?,
            modificato_il = ?
        WHERE id = ?
        """,
        (
            data,
            ambiente.strip(),
            descrizione.strip(),
            priorita,
            assegnato_a,
            stato,
            note_tecnico.strip(),
            now,
            ticket_id,
        ),
    )

    refresh_technician_drive_file(
        assegnato_a
    )

    if (
        old_assigned_to
        and old_assigned_to != assegnato_a
    ):

        refresh_technician_drive_file(
            old_assigned_to
        )


# ============================================================
# AGGIORNAMENTO TECNICO
# ============================================================

def update_ticket_technician(
    ticket_id,
    stato,
    note_tecnico,
):

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    execute(
        """
        UPDATE ticket
        SET
            stato = ?,
            note_tecnico = ?,
            modificato_il = ?
        WHERE id = ?
        AND assegnato_a = ?
        """,
        (
            stato,
            note_tecnico.strip(),
            now,
            ticket_id,
            st.session_state.username,
        ),
    )


# ============================================================
# ELIMINAZIONE
# ============================================================

def delete_ticket(ticket_id):

    ticket = execute(
        """
        SELECT assegnato_a
        FROM ticket
        WHERE id = ?
        """,
        (ticket_id,),
        fetchone=True,
    )

    execute(
        """
        DELETE FROM ticket
        WHERE id = ?
        """,
        (ticket_id,),
    )

    if ticket:
        refresh_technician_drive_file(
            ticket[0]
        )


# ============================================================
# EXCEL
# ============================================================

def dataframe_to_excel(
    df,
    username=None,
    version=None,
    generated_at=None,
):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Ticket",
        )

        if username:

            info_df = pd.DataFrame(
                {
                    "Parametro": [
                        "Tecnico",
                        "Versione",
                        "Generato il",
                    ],
                    "Valore": [
                        username,
                        version,
                        generated_at,
                    ],
                }
            )

            info_df.to_excel(
                writer,
                index=False,
                sheet_name="INFO",
            )

            writer.book["INFO"].sheet_state = (
                "hidden"
            )

    output.seek(0)

    return output.getvalue()


def create_technician_excel(
    username,
    increment_version=True,
):

    df = get_technician_tickets(
        username
    )

    if df.empty:
        return None

    columns = [
        "id",
        "data",
        "ambiente",
        "descrizione",
        "priorita",
        "stato",
        "note_tecnico",
        "assegnato_a",
    ]

    df = df[columns].copy()

    filename = (
        f"ticket_{username}_da_gestire.xlsx"
    )

    if increment_version:

        version = create_file_version(
            username,
            filename,
        )

    else:

        info = get_file_info(
            username
        )

        if info:

            version = info[1]

        else:

            version = create_file_version(
                username,
                filename,
            )

    generated_at = datetime.now().isoformat(
        timespec="seconds"
    )

    excel_bytes = dataframe_to_excel(
        df,
        username,
        version,
        generated_at,
    )

    return {
        "bytes": excel_bytes,
        "filename": filename,
        "version": version,
        "generated_at": generated_at,
    }


# ============================================================
# SINCRONIZZAZIONE DRIVE
# ============================================================

def sync_technician_file_to_drive(
    username,
    increment_version=True,
):

    if not drive_available():
        return None

    excel = create_technician_excel(
        username,
        increment_version,
    )

    if excel is None:
        return None

    folders = (
        get_technician_drive_folders(
            username
        )
    )

    result = upload_or_update_drive_file(
        excel["bytes"],
        excel["filename"],
        folders["da_gestire"],
    )

    return {
        **excel,
        "drive_file": result,
    }


def refresh_technician_drive_file(
    username
):

    if not drive_available():
        return

    try:

        sync_technician_file_to_drive(
            username,
            increment_version=True,
        )

    except Exception as e:

        # Non blocchiamo il salvataggio del ticket
        # se Drive non è disponibile.
        print(
            "Errore sincronizzazione Drive:",
            e,
        )


# ============================================================
# IMPORT EXCEL
# ============================================================

def process_delivery_file(
    uploaded_file
):

    username = (
        st.session_state.username
    )

    errors = []

    expected_filename = (
        f"ticket_{username}_da_gestire.xlsx"
    )

    if uploaded_file.name != expected_filename:

        errors.append(
            f"Nome file non valido. "
            f"Deve essere: {expected_filename}"
        )

        return False, errors

    try:

        uploaded_file.seek(0)

        excel_file = pd.ExcelFile(
            uploaded_file
        )

        if "Ticket" not in (
            excel_file.sheet_names
        ):

            errors.append(
                "Il file non contiene "
                "il foglio Ticket."
            )

            return False, errors

        df = pd.read_excel(
            uploaded_file,
            sheet_name="Ticket",
        )

    except Exception as e:

        errors.append(
            f"Errore lettura Excel: {e}"
        )

        return False, errors

    required_columns = {
        "id",
        "stato",
        "note_tecnico",
        "assegnato_a",
    }

    missing = (
        required_columns
        - set(df.columns)
    )

    if missing:

        errors.append(
            "Colonne mancanti: "
            + ", ".join(
                sorted(missing)
            )
        )

        return False, errors

    # --------------------------------------------------------
    # CONTROLLO TECNICO
    # --------------------------------------------------------

    if not all(
        df["assegnato_a"]
        .astype(str)
        .str.strip()
        == username
    ):

        errors.append(
            "Il file contiene ticket "
            "assegnati ad altri utenti."
        )

        return False, errors

    # --------------------------------------------------------
    # CONTROLLO ID E STATI
    # --------------------------------------------------------

    for _, row in df.iterrows():

        try:

            ticket_id = int(
                row["id"]
            )

        except Exception:

            errors.append(
                f"ID non valido: {row['id']}"
            )

            continue

        stato = str(
            row["stato"]
        ).strip()

        if stato not in STATI:

            errors.append(
                f"Ticket {ticket_id}: "
                f"stato '{stato}' non valido."
            )

            continue

        ticket = execute(
            """
            SELECT id, assegnato_a
            FROM ticket
            WHERE id = ?
            """,
            (ticket_id,),
            fetchone=True,
        )

        if not ticket:

            errors.append(
                f"Ticket {ticket_id} "
                "non esiste."
            )

            continue

        if ticket[1] != username:

            errors.append(
                f"Ticket {ticket_id}: "
                "non assegnato a questo tecnico."
            )

    if errors:
        return False, errors

    # --------------------------------------------------------
    # AGGIORNA DATABASE
    # --------------------------------------------------------

    updated = 0

    for _, row in df.iterrows():

        ticket_id = int(
            row["id"]
        )

        stato = str(
            row["stato"]
        ).strip()

        if pd.isna(
            row["note_tecnico"]
        ):

            note = ""

        else:

            note = str(
                row["note_tecnico"]
            ).strip()

        update_ticket_technician(
            ticket_id,
            stato,
            note,
        )

        updated += 1

    # --------------------------------------------------------
    # ARCHIVIO DRIVE
    # --------------------------------------------------------

    if drive_available():

        try:

            folders = (
                get_technician_drive_folders(
                    username
                )
            )

            service = get_drive_service()

            current_file = find_drive_file(
                service,
                uploaded_file.name,
                folders["da_gestire"],
            )

            uploaded_file.seek(0)

            managed_filename = (
                f"ticket_{username}_"
                f"gestito_"
                f"{datetime.now():%Y%m%d_%H%M%S}.xlsx"
            )

            upload_file_to_drive(
                uploaded_file.read(),
                managed_filename,
                folders["gestiti"],
            )

            if current_file:

                move_drive_file(
                    current_file["id"],
                    folders["gestiti"],
                )

            # Genera il nuovo file di lavoro
            sync_technician_file_to_drive(
                username,
                increment_version=True,
            )

        except Exception as e:

            return False, [
                "Database aggiornato, ma errore "
                f"Google Drive: {e}"
            ]

    return True, [
        f"Ticket aggiornati: {updated}",
        "Il file consegnato è stato archiviato.",
        "È stato generato un nuovo file di lavoro.",
    ]


# ============================================================
# LOGIN
# ============================================================

def login_page():

    st.title(
        "🔐 Accesso al Sistema Ticket"
    )

    st.markdown(
        "### Benvenuto"
    )

    st.caption(
        "Inserisci le tue credenziali "
        "per accedere alla piattaforma."
    )

    col1, col2, col3 = st.columns(
        [1, 1.4, 1]
    )

    with col2:

        with st.container(
            border=True
        ):

            st.subheader(
                "🔑 Login"
            )

            username = st.text_input(
                "Username",
                placeholder="Inserisci username",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Inserisci password",
            )

            if st.button(
                "ACCEDI",
                type="primary",
                use_container_width=True,
            ):

                user = execute(
                    """
                    SELECT password, ruolo
                    FROM utenti
                    WHERE username = ?
                    """,
                    (username.strip(),),
                    fetchone=True,
                )

                if (
                    user
                    and check_hash(
                        password,
                        user[0],
                    )
                ):

                    st.session_state.logged_in = True
                    st.session_state.username = (
                        username.strip()
                    )
                    st.session_state.ruolo = (
                        user[1]
                    )

                    st.rerun()

                else:

                    st.error(
                        "Username o password errati."
                    )

    st.info(
        "Accesso iniziale: "
        "admin / admin123"
    )


# ============================================================
# SIDEBAR
# ============================================================

def show_sidebar():

    st.sidebar.title(
        "🎫 Gestione Ticket"
    )

    st.sidebar.success(
        f"👤 {st.session_state.username}"
    )

    st.sidebar.write(
        f"Ruolo: **{st.session_state.ruolo}**"
    )

    st.sidebar.divider()

    if st.sidebar.button(
        "🚪 Logout",
        use_container_width=True,
    ):

        logout()


# ============================================================
# KPI
# ============================================================

def show_kpi(df):

    totale = len(df)

    aperti = (
        df["stato"] == "Aperto"
    ).sum()

    in_corso = (
        df["stato"] == "In Corso"
    ).sum()

    risolti = (
        df["stato"] == "Risolto"
    ).sum()

    chiusi = (
        df["stato"] == "Chiuso"
    ).sum()

    cols = st.columns(5)

    cols[0].metric(
        "🎫 Ticket Totali",
        totale,
    )

    cols[1].metric(
        "🔴 Aperti",
        aperti,
    )

    cols[2].metric(
        "🟠 In Corso",
        in_corso,
    )

    cols[3].metric(
        "🟢 Risolti",
        risolti,
    )

    cols[4].metric(
        "⚫ Chiusi",
        chiusi,
    )


# ============================================================
# FILTRI
# ============================================================

def filter_tickets(df):

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        search = st.text_input(
            "🔎 Cerca",
            placeholder=(
                "Descrizione o ambiente"
            ),
        )

    with col2:

        stato = st.selectbox(
            "Stato",
            ["Tutti"] + STATI,
        )

    with col3:

        priorita = st.selectbox(
            "Priorità",
            ["Tutte"] + PRIORITA,
        )

    with col4:

        assigned = sorted(
            df["assegnato_a"]
            .dropna()
            .unique()
            .tolist()
        )

        tecnico = st.selectbox(
            "Assegnato a",
            ["Tutti"] + assigned,
        )

    result = df.copy()

    if search:

        mask = (
            result["descrizione"]
            .astype(str)
            .str.contains(
                search,
                case=False,
                na=False,
            )
            |
            result["ambiente"]
            .astype(str)
            .str.contains(
                search,
                case=False,
                na=False,
            )
        )

        result = result[mask]

    if stato != "Tutti":

        result = result[
            result["stato"] == stato
        ]

    if priorita != "Tutte":

        result = result[
            result["priorita"] == priorita
        ]

    if tecnico != "Tutti":

        result = result[
            result["assegnato_a"] == tecnico
        ]

    return result


# ============================================================
# TABELLA ADMIN
# ============================================================

def show_table(df):

    if df.empty:

        st.info(
            "Nessun ticket trovato."
        )

        return

    display = df[
        [
            "id",
            "data",
            "ambiente",
            "descrizione",
            "priorita",
            "assegnato_a",
            "creato_da",
            "stato",
            "note_tecnico",
        ]
    ].copy()

    display.columns = [
        "ID",
        "Data",
        "Ambiente",
        "Descrizione",
        "Priorità",
        "Assegnato a",
        "Creato da",
        "Stato",
        "Note tecnico",
    ]

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )

    excel = dataframe_to_excel(
        display
    )

    st.download_button(
        "📥 Scarica Excel",
        data=excel,
        file_name=(
            f"ticket_{datetime.now():%Y%m%d_%H%M}.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
    )


# ============================================================
# NUOVO TICKET
# ============================================================

def new_ticket_section(
    users
):

    st.subheader(
        "➕ Nuovo Ticket"
    )

    if not users:

        st.error(
            "Non esistono tecnici disponibili."
        )

        return

    with st.form(
        "new_ticket"
    ):

        col1, col2 = st.columns(2)

        with col1:

            data = st.date_input(
                "Data",
                datetime.now().date(),
            )

            ambiente = st.text_input(
                "Ambiente",
                placeholder=(
                    "Es. PC-01, Server, Ufficio..."
                ),
            )

            priorita = st.selectbox(
                "Priorità",
                PRIORITA,
            )

        with col2:

            descrizione = st.text_area(
                "Descrizione",
                height=130,
            )

            assegnato_a = st.selectbox(
                "Assegnato a",
                users,
            )

        submit = st.form_submit_button(
            "🎫 CREA TICKET",
            type="primary",
            use_container_width=True,
        )

        if submit:

            if not ambiente.strip():

                st.error(
                    "Inserisci l'ambiente."
                )

                return

            if not descrizione.strip():

                st.error(
                    "Inserisci la descrizione."
                )

                return

            create_ticket(
                data.isoformat(),
                ambiente,
                descrizione,
                priorita,
                assegnato_a,
                st.session_state.username,
            )

            st.success(
                "Ticket creato correttamente."
            )

            st.rerun()


# ============================================================
# MODIFICA ADMIN
# ============================================================

def admin_edit_section(
    df,
    users,
):

    if df.empty:

        st.info(
            "Nessun ticket disponibile."
        )

        return

    st.subheader(
        "✏️ Modifica Ticket"
    )

    ticket_id = st.selectbox(
        "Ticket",
        df["id"].tolist(),
        key="admin_ticket",
    )

    row = df[
        df["id"] == ticket_id
    ].iloc[0]

    with st.form(
        "edit_admin"
    ):

        col1, col2 = st.columns(2)

        with col1:

            try:

                ticket_date = (
                    pd.to_datetime(
                        row["data"]
                    ).date()
                )

            except Exception:

                ticket_date = (
                    datetime.now().date()
                )

            data = st.date_input(
                "Data",
                ticket_date,
            )

            ambiente = st.text_input(
                "Ambiente",
                row["ambiente"],
            )

            priorita = st.selectbox(
                "Priorità",
                PRIORITA,
                index=(
                    PRIORITA.index(
                        row["priorita"]
                    )
                    if row["priorita"]
                    in PRIORITA
                    else 0
                ),
            )

            assegnato_a = st.selectbox(
                "Assegnato a",
                users,
                index=(
                    users.index(
                        row["assegnato_a"]
                    )
                    if row["assegnato_a"]
                    in users
                    else 0
                ),
            )

        with col2:

            stato = st.selectbox(
                "Stato",
                STATI,
                index=(
                    STATI.index(
                        row["stato"]
                    )
                    if row["stato"]
                    in STATI
                    else 0
                ),
            )

            descrizione = st.text_area(
                "Descrizione",
                row["descrizione"],
                height=130,
            )

            note = st.text_area(
                "Note tecnico",
                row["note_tecnico"] or "",
                height=100,
            )

        save = st.form_submit_button(
            "💾 SALVA",
            type="primary",
            use_container_width=True,
        )

        if save:

            update_ticket_admin(
                ticket_id,
                data.isoformat(),
                ambiente,
                descrizione,
                priorita,
                assegnato_a,
                stato,
                note,
            )

            st.success(
                "Ticket aggiornato."
            )

            st.rerun()


# ============================================================
# ELIMINA TICKET
# ============================================================

def admin_delete_section(
    df
):

    if df.empty:
        return

    st.subheader(
        "🗑️ Elimina Ticket"
    )

    ticket_id = st.selectbox(
        "Ticket da eliminare",
        df["id"].tolist(),
        key="delete_ticket",
    )

    confirm = st.checkbox(
        "Confermo l'eliminazione definitiva.",
        key="confirm_delete",
    )

    if st.button(
        "🗑️ ELIMINA",
        disabled=not confirm,
    ):

        delete_ticket(
            ticket_id
        )

        st.success(
            "Ticket eliminato."
        )

        st.rerun()


# ============================================================
# SCHEDA TECNICO - I MIEI TICKET
# ============================================================

def technician_section():

    username = (
        st.session_state.username
    )

    df = get_technician_tickets(
        username
    )

    st.subheader(
        "📋 I miei Ticket"
    )

    if df.empty:

        st.info(
            "Non hai ticket assegnati."
        )

        return

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "🎫 Totali",
        len(df),
    )

    col2.metric(
        "🔴 Aperti",
        len(
            df[
                df["stato"] == "Aperto"
            ]
        ),
    )

    col3.metric(
        "🟠 In Corso",
        len(
            df[
                df["stato"] == "In Corso"
            ]
        ),
    )

    col4.metric(
        "🟢 Risolti/Chiusi",
        len(
            df[
                df["stato"].isin(
                    [
                        "Risolto",
                        "Chiuso",
                    ]
                )
            ]
        ),
    )

    st.divider()

    display = df[
        [
            "id",
            "data",
            "ambiente",
            "descrizione",
            "priorita",
            "stato",
            "note_tecnico",
        ]
    ].copy()

    display.columns = [
        "ID",
        "Data",
        "Ambiente",
        "Descrizione",
        "Priorità",
        "Stato",
        "Note tecnico",
    ]

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# SCHEDA CONSEGNA TICKET
# ============================================================

def technician_delivery_section():

    username = (
        st.session_state.username
    )

    st.subheader(
        "📤 Consegna Ticket"
    )

    st.caption(
        "Scarica il file di lavoro, completa "
        "gli interventi e ricaricalo qui."
    )

    # --------------------------------------------------------
    # GOOGLE DRIVE NON CONFIGURATO
    # --------------------------------------------------------

    if not drive_available():

        st.warning(
            "Google Drive non è ancora configurato."
        )

        st.info(
            "Per ora puoi utilizzare la modifica "
            "diretta dei ticket dalla scheda "
            "'I miei Ticket'."
        )

        st.markdown(
            """
            ### Flusso Google Drive

            Quando Drive sarà configurato, qui compariranno:

            1. Il file Excel da gestire.
            2. Il pulsante per scaricarlo.
            3. Il caricamento del file completato.
            4. I controlli automatici.
            5. L'archiviazione nella cartella `Gestiti`.
            6. La generazione del nuovo file di lavoro.
            """
        )

        return

    try:

        folders = (
            get_technician_drive_folders(
                username
            )
        )

        # ----------------------------------------------------
        # INFORMAZIONI FILE
        # ----------------------------------------------------

        current_info = get_file_info(
            username
        )

        st.write(
            "### 📄 File di lavoro"
        )

        if current_info:

            _, version, generated_at, filename = (
                current_info
            )

            st.info(
                f"**Versione:** {version}  \n"
                f"**Generato:** {generated_at}  \n"
                f"**File:** `{filename}`"
            )

        # ----------------------------------------------------
        # CREA FILE SE NON ESISTE
        # ----------------------------------------------------

        if not current_info:

            if st.button(
                "📄 GENERA FILE DI LAVORO",
                type="primary",
                use_container_width=True,
            ):

                result = (
                    sync_technician_file_to_drive(
                        username,
                        increment_version=True,
                    )
                )

                if result:

                    st.success(
                        "File creato su Google Drive."
                    )

                    st.rerun()

                else:

                    st.error(
                        "Impossibile creare il file."
                    )

                return

        # ----------------------------------------------------
        # FILE SU DRIVE
        # ----------------------------------------------------

        files = list_drive_files(
            folders["da_gestire"]
        )

        current_file = None

        for file in files:

            if (
                current_info
                and file["name"]
                == current_info[3]
            ):

                current_file = file
                break

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        if current_file:

            file_bytes = (
                download_drive_file(
                    current_file["id"]
                )
            )

            st.download_button(
                "⬇️ SCARICA FILE DI LAVORO",
                data=file_bytes,
                file_name=current_file["name"],
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                use_container_width=True,
            )

        else:

            st.warning(
                "Il file corrente non è presente su Drive."
            )

            if st.button(
                "🔄 RIGENERA FILE",
                use_container_width=True,
            ):

                sync_technician_file_to_drive(
                    username,
                    increment_version=True,
                )

                st.success(
                    "File rigenerato."
                )

                st.rerun()

        st.divider()

        # ----------------------------------------------------
        # UPLOAD
        # ----------------------------------------------------

        st.write(
            "### 📤 Consegna il file completato"
        )

        uploaded = st.file_uploader(
            "Seleziona il file Excel completato",
            type=["xlsx"],
            key="delivery_file",
        )

        if uploaded:

            st.write(
                f"📄 **{uploaded.name}**"
            )

            if st.button(
                "🚀 CONSEGNA TICKET",
                type="primary",
                use_container_width=True,
            ):

                success, messages = (
                    process_delivery_file(
                        uploaded
                    )
                )

                if success:

                    st.success(
                        "Consegna completata."
                    )

                    for message in messages:
                        st.info(message)

                    st.rerun()

                else:

                    st.error(
                        "La consegna non è stata accettata."
                    )

                    for message in messages:
                        st.warning(message)

    except Exception as e:

        st.error(
            f"Errore Google Drive: {e}"
        )


# ============================================================
# GESTIONE UTENTI
# ============================================================

def users_section():

    if not is_admin():

        st.warning(
            "Area riservata agli amministratori."
        )

        return

    st.subheader(
        "👥 Gestione Utenti"
    )

    users = get_users()

    users_df = pd.DataFrame(
        users,
        columns=[
            "Username",
            "Ruolo",
        ],
    )

    st.dataframe(
        users_df,
        use_container_width=True,
        hide_index=True,
    )

    tab1, tab2, tab3 = st.tabs(
        [
            "➕ Crea",
            "🔑 Password",
            "🗑️ Elimina",
        ]
    )

    # --------------------------------------------------------
    # CREA
    # --------------------------------------------------------

    with tab1:

        with st.form(
            "create_user"
        ):

            username = st.text_input(
                "Username"
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            confirm = st.text_input(
                "Conferma password",
                type="password",
            )

            ruolo = st.selectbox(
                "Ruolo",
                RUOLI,
            )

            submit = st.form_submit_button(
                "CREA UTENTE",
                type="primary",
            )

            if submit:

                username = username.strip()

                if not username:

                    st.error(
                        "Username obbligatorio."
                    )

                elif not password:

                    st.error(
                        "Password obbligatoria."
                    )

                elif password != confirm:

                    st.error(
                        "Le password non coincidono."
                    )

                else:

                    exists = execute(
                        """
                        SELECT username
                        FROM utenti
                        WHERE username = ?
                        """,
                        (username,),
                        fetchone=True,
                    )

                    if exists:

                        st.error(
                            "Username già esistente."
                        )

                    else:

                        execute(
                            """
                            INSERT INTO utenti
                            (username, password, ruolo)
                            VALUES (?, ?, ?)
                            """,
                            (
                                username,
                                make_hash(password),
                                ruolo,
                            ),
                        )

                        st.success(
                            "Utente creato."
                        )

                        st.rerun()

    # --------------------------------------------------------
    # PASSWORD
    # --------------------------------------------------------

    with tab2:

        usernames = [
            row[0]
            for row in users
        ]

        if usernames:

            selected = st.selectbox(
                "Utente",
                usernames,
            )

            new_password = st.text_input(
                "Nuova password",
                type="password",
            )

            confirm = st.text_input(
                "Conferma password",
                type="password",
            )

            if st.button(
                "🔑 CAMBIA PASSWORD",
                type="primary",
            ):

                if not new_password:

                    st.error(
                        "Inserisci la password."
                    )

                elif new_password != confirm:

                    st.error(
                        "Le password non coincidono."
                    )

                else:

                    execute(
                        """
                        UPDATE utenti
                        SET password = ?
                        WHERE username = ?
                        """,
                        (
                            make_hash(
                                new_password
                            ),
                            selected,
                        ),
                    )

                    st.success(
                        "Password modificata."
                    )

    # --------------------------------------------------------
    # ELIMINA
    # --------------------------------------------------------

    with tab3:

        deletable = [
            row[0]
            for row in users
            if row[0] != "admin"
            and row[0]
            != st.session_state.username
        ]

        if deletable:

            selected = st.selectbox(
                "Utente",
                deletable,
            )

            if st.button(
                "🗑️ ELIMINA UTENTE",
            ):

                execute(
                    """
                    DELETE FROM utenti
                    WHERE username = ?
                    """,
                    (selected,),
                )

                st.success(
                    "Utente eliminato."
                )

                st.rerun()

        else:

            st.info(
                "Nessun utente eliminabile."
            )


# ============================================================
# GRAFICI
# ============================================================

def show_charts(df):

    if df.empty:
        return

    st.subheader(
        "📊 Analisi"
    )

    col1, col2 = st.columns(2)

    with col1:

        status = (
            df["stato"]
            .value_counts()
            .reset_index()
        )

        status.columns = [
            "stato",
            "numero",
        ]

        fig = px.pie(
            status,
            names="stato",
            values="numero",
            hole=0.4,
            title="Ticket per stato",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    with col2:

        priority = (
            df["priorita"]
            .value_counts()
            .reindex(
                PRIORITA,
                fill_value=0,
            )
            .reset_index()
        )

        priority.columns = [
            "priorita",
            "numero",
        ]

        fig = px.bar(
            priority,
            x="priorita",
            y="numero",
            color="priorita",
            title="Ticket per priorità",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ============================================================
# DASHBOARD ADMIN
# ============================================================

def admin_dashboard():

    df = get_tickets()

    show_kpi(df)

    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📊 Dashboard",
            "➕ Nuovo Ticket",
            "✏️ Gestione",
            "☁️ Google Drive",
            "👥 Utenti",
        ]
    )

    # --------------------------------------------------------
    # DASHBOARD
    # --------------------------------------------------------

    with tab1:

        filtered = filter_tickets(
            df
        )

        show_table(
            filtered
        )

        show_charts(
            filtered
        )

    # --------------------------------------------------------
    # NUOVO TICKET
    # --------------------------------------------------------

    with tab2:

        users = [
            row[0]
            for row in get_users()
        ]

        new_ticket_section(
            users
        )

    # --------------------------------------------------------
    # GESTIONE
    # --------------------------------------------------------

    with tab3:

        filtered = filter_tickets(
            df
        )

        users = [
            row[0]
            for row in get_users()
        ]

        admin_edit_section(
            filtered,
            users,
        )

        st.divider()

        admin_delete_section(
            filtered
        )

    # --------------------------------------------------------
    # DRIVE
    # --------------------------------------------------------

    with tab4:

        st.subheader(
            "☁️ Google Drive"
        )

        if not drive_available():

            st.warning(
                "Google Drive non configurato."
            )

            st.info(
                "L'applicazione funziona comunque "
                "con SQLite ed Excel."
            )

        else:

            st.success(
                "Google Drive collegato."
            )

            if st.button(
                "📁 CREA STRUTTURA DRIVE",
                type="primary",
            ):

                try:

                    get_drive_structure()

                    st.success(
                        "Struttura Drive pronta."
                    )

                except Exception as e:

                    st.error(
                        f"Errore: {e}"
                    )

    # --------------------------------------------------------
    # UTENTI
    # --------------------------------------------------------

    with tab5:

        users_section()


# ============================================================
# DASHBOARD TECNICO
# ============================================================

def technician_dashboard():

    tab1, tab2, tab3 = st.tabs(
        [
            "📋 I miei Ticket",
            "📤 Consegna Ticket",
            "📊 Statistiche",
        ]
    )

    with tab1:

        technician_section()

    with tab2:

        technician_delivery_section()

    with tab3:

        df = get_technician_tickets(
            st.session_state.username
        )

        show_kpi(df)

        show_charts(df)


# ============================================================
# MAIN
# ============================================================

if not st.session_state.logged_in:

    login_page()

else:

    show_sidebar()

    st.title(
        "🎫 Sistema Gestione Ticket"
    )

    st.caption(
        "Crea, assegna e monitora "
        "le richieste di assistenza."
    )

    if is_admin():

        admin_dashboard()

    else:

        technician_dashboard()
