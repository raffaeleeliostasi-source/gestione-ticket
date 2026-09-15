import re
from datetime import datetime

import streamlit as st
from supabase import create_client, Client


# ============================================================
# CONFIGURAZIONE
# ============================================================

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

STATI = [
    "Aperto",
    "In Lavorazione",
    "Risolto",
    "Chiuso",
]

PRIORITA = [
    "Bassa",
    "Media",
    "Alta",
    "Urgente",
]

BUCKET_ALLEGATI = "allegati"


# ============================================================
# COLLEGAMENTO SUPABASE
# ============================================================

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = get_supabase()


# ============================================================
# UTILITÀ
# ============================================================

def _now():
    return datetime.now().isoformat(timespec="seconds")


def sanitizza_nome_file(nome):
    nome = str(nome or "").strip()
    nome = re.sub(r"[^A-Za-z0-9._-]", "_", nome)
    return nome[:180] or "allegato"


def format_data(value):
    if not value:
        return ""

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).strftime("%d/%m/%Y %H:%M")

    except Exception:
        return str(value)


# ============================================================
# TICKET
# ============================================================

def get_tickets(limit=500):
    try:
        risposta = (
            supabase.table("tickets")
            .select("*")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return risposta.data or []

    except Exception as e:
        st.error(f"Errore caricamento ticket: {e}")
        return []


def get_ticket(ticket_id):
    try:
        risposta = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )

        return risposta.data[0] if risposta.data else None

    except Exception as e:
        st.error(f"Errore caricamento ticket: {e}")
        return None


def get_tickets_tecnico(tecnico, limit=500):
    try:
        risposta = (
            supabase.table("tickets")
            .select("*")
            .eq("assegnato_a", tecnico)
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )

        return risposta.data or []

    except Exception as e:
        st.error(f"Errore caricamento ticket tecnico: {e}")
        return []


def crea_ticket(
    titolo,
    descrizione,
    categoria,
    priorita,
    creato_da,
    assegnato_a=None,
):
    try:
        dati = {
            "titolo": titolo,
            "descrizione": descrizione,
            "categoria": categoria,
            "priorita": priorita,
            "creato_da": creato_da,
            "stato": "Aperto",
        }

        if assegnato_a:
            dati["assegnato_a"] = assegnato_a

        risposta = (
            supabase.table("tickets")
            .insert(dati)
            .execute()
        )

        return risposta.data[0] if risposta.data else None

    except Exception as e:
        st.error(f"Errore creazione ticket: {e}")
        return None


def aggiorna_stato_ticket(ticket_id, stato):
    if stato not in STATI:
        st.error(f"Stato non valido: {stato}")
        return False

    try:
        supabase.table("tickets").update(
            {
                "stato": stato,
                "modificato_il": _now(),
            }
        ).eq("id", ticket_id).execute()

        return True

    except Exception as e:
        # Compatibilità nel caso in cui modificato_il non esista
        try:
            supabase.table("tickets").update(
                {
                    "stato": stato,
                }
            ).eq("id", ticket_id).execute()

            return True

        except Exception as e2:
            st.error(f"Errore aggiornamento stato ticket: {e2}")
            return False


def chiudi_ticket(ticket_id, chiuso_da):
    try:
        dati = {
            "stato": "Chiuso",
            "chiuso_da": chiuso_da,
            "data_chiusura": _now(),
            "modificato_il": _now(),
        }

        try:
            supabase.table("tickets").update(
                dati
            ).eq("id", ticket_id).execute()

        except Exception:
            # Compatibilità se modificato_il non esiste
            dati.pop("modificato_il", None)

            supabase.table("tickets").update(
                dati
            ).eq("id", ticket_id).execute()

        return True

    except Exception as e:
        st.error(f"Errore chiusura ticket: {e}")
        return False


# ============================================================
# UTENTI
# ============================================================

def get_utenti():
    try:
        risposta = (
            supabase.table("utenti")
            .select("*")
            .order("username")
            .execute()
        )

        return risposta.data or []

    except Exception as e:
        st.error(f"Errore caricamento utenti: {e}")
        return []


def get_utente(username):
    try:
        risposta = (
            supabase.table("utenti")
            .select("*")
            .eq("username", username)
            .limit(1)
            .execute()
        )

        return risposta.data[0] if risposta.data else None

    except Exception as e:
        st.error(f"Errore caricamento utente: {e}")
        return None


def get_tecnici_attivi():
    try:
        risposta = (
            supabase.table("utenti")
            .select("*")
            .eq("ruolo", "tecnico")
            .order("username")
            .execute()
        )

        utenti = risposta.data or []

        return [
            u for u in utenti
            if u.get("attivo", True) is not False
        ]

    except Exception as e:
        st.error(f"Errore caricamento tecnici: {e}")
        return []


def crea_utente(username, password, ruolo, attivo=True):
    try:
        dati = {
            "username": username,
            "password": password,
            "ruolo": ruolo,
            "attivo": attivo,
        }

        risposta = (
            supabase.table("utenti")
            .insert(dati)
            .execute()
        )

        return risposta.data[0] if risposta.data else None

    except Exception as e:
        st.error(f"Errore creazione utente: {e}")
        return None


def aggiorna_utente(username, dati):
    try:
        (
            supabase.table("utenti")
            .update(dati)
            .eq("username", username)
            .execute()
        )

        return True

    except Exception as e:
        st.error(f"Errore aggiornamento utente: {e}")
        return False


def aggiorna_password(username, password):
    try:
        (
            supabase.table("utenti")
            .update({"password": password})
            .eq("username", username)
            .execute()
        )

        return True

    except Exception as e:
        st.error(f"Errore aggiornamento password: {e}")
        return False


# ============================================================
# CATEGORIE
# ============================================================

def get_categorie(solo_attive=False):
    try:
        query = (
            supabase.table("categorie")
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


def crea_categoria(nome, attivo=True):
    try:
        dati = {
            "nome": nome.strip(),
            "attivo": attivo,
        }

        risposta = (
            supabase.table("categorie")
            .insert(dati)
            .execute()
        )

        return risposta.data[0] if risposta.data else None

    except Exception as e:
        st.error(f"Errore creazione categoria: {e}")
        return None


def modifica_categoria(categoria_id, vecchio_nome, nuovo_nome, attivo=True):
    try:
        nuovo_nome = nuovo_nome.strip()

        (
            supabase.table("categorie")
            .update(
                {
                    "nome": nuovo_nome,
                    "attivo": attivo,
                }
            )
            .eq("id", categoria_id)
            .execute()
        )

        # Mantiene coerenti i ticket storici
        if vecchio_nome and nuovo_nome and vecchio_nome != nuovo_nome:
            (
                supabase.table("tickets")
                .update({"categoria": nuovo_nome})
                .eq("categoria", vecchio_nome)
                .execute()
            )

        return True

    except Exception as e:
        st.error(f"Errore modifica categoria: {e}")
        return False


# ============================================================
# ALLEGATI DEL TICKET
# ============================================================

def salva_allegato(ticket_id, file):
    if file is None:
        return None

    try:
        contenuto = file.getvalue()

        if len(contenuto) > MAX_FILE_SIZE_BYTES:
            st.error(
                f"Il file supera il limite massimo di "
                f"{MAX_FILE_SIZE_MB} MB."
            )
            return None

        nome_originale = getattr(file, "name", "allegato")
        nome_file = sanitizza_nome_file(nome_originale)

        percorso = f"ticket_{ticket_id}/{nome_file}"

        supabase.storage.from_(BUCKET_ALLEGATI).upload(
            percorso,
            contenuto,
            {
                "content-type": getattr(
                    file,
                    "type",
                    "application/octet-stream",
                ),
                "upsert": "true",
            },
        )

        dati = {
            "ticket_id": ticket_id,
            "nome_file": nome_originale,
            "percorso_file": percorso,
        }

        risposta = (
            supabase.table("ticket_allegati")
            .insert(dati)
            .execute()
        )

        return risposta.data[0] if risposta.data else None

    except Exception as e:
        st.error(f"Errore salvataggio allegato: {e}")
        return None


def get_allegati(ticket_id):
    try:
        risposta = (
            supabase.table("ticket_allegati")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("id")
            .execute()
        )

        return risposta.data or []

    except Exception as e:
        st.error(f"Errore caricamento allegati: {e}")
        return []


def scarica_allegato(percorso):
    try:
        return (
            supabase.storage
            .from_(BUCKET_ALLEGATI)
            .download(percorso)
        )

    except Exception as e:
        st.error(f"Errore download allegato: {e}")
        return None


# ============================================================
# INTERVENTI TECNICI
# ============================================================

def get_interventi(ticket_id):
    """
    Restituisce TUTTI gli interventi del ticket.

    Ogni intervento è una riga distinta.
    L'ordinamento è cronologico crescente.
    """

    try:
        risposta = (
            supabase.table("ticket_interventi")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("data_intervento", desc=False)
            .order("id", desc=False)
            .execute()
        )

        return risposta.data or []

    except Exception as e:
        st.error(f"Errore caricamento cronologia interventi: {e}")
        return []


def get_intervento(ticket_id):
    """
    Compatibilità con il vecchio codice.

    Restituisce l'ultimo intervento del ticket.
    Il nuovo codice dovrebbe utilizzare get_interventi().
    """

    interventi = get_interventi(ticket_id)

    if not interventi:
        return None

    return interventi[-1]


def get_intervento_by_id(intervento_id):
    """
    Recupera uno specifico intervento tramite il suo ID.
    """

    try:
        risposta = (
            supabase.table("ticket_interventi")
            .select("*")
            .eq("id", intervento_id)
            .limit(1)
            .execute()
        )

        return risposta.data[0] if risposta.data else None

    except Exception as e:
        st.error(f"Errore caricamento intervento: {e}")
        return None


def salva_intervento_tecnico(
    ticket_id,
    tecnico,
    descrizione,
    stato,
    data_intervento=None,
):
    """
    NUOVO MODELLO:

    Ogni salvataggio crea SEMPRE un nuovo intervento.

    Non viene mai eseguito UPDATE su un intervento precedente.
    """

    try:
        # ----------------------------------------------------
        # Controllo ticket
        # ----------------------------------------------------

        ticket = get_ticket(ticket_id)

        if not ticket:
            st.error("Ticket non trovato.")
            return None

        # ----------------------------------------------------
        # Controllo assegnazione
        # ----------------------------------------------------

        assegnato_a = ticket.get("assegnato_a")

        if assegnato_a and str(assegnato_a) != str(tecnico):
            st.error(
                "Il ticket non è assegnato a questo tecnico."
            )
            return None

        # ----------------------------------------------------
        # Controllo stato ticket
        # ----------------------------------------------------

        stato_ticket = str(
            ticket.get("stato", "Aperto")
        ).strip()

        if stato_ticket in {"Risolto", "Chiuso"}:
            st.error(
                "Questo ticket non può più essere modificato "
                "dal tecnico."
            )
            return None

        # ----------------------------------------------------
        # Controllo stato intervento
        # ----------------------------------------------------

        stati_tecnico = {
            "Aperto",
            "In Lavorazione",
            "Risolto",
        }

        if stato not in stati_tecnico:
            st.error(
                f"Stato intervento non valido: {stato}"
            )
            return None

        # ----------------------------------------------------
        # Controllo descrizione
        # ----------------------------------------------------

        descrizione = str(descrizione or "").strip()

        if not descrizione:
            st.error(
                "La descrizione dell'intervento è obbligatoria."
            )
            return None

        # ----------------------------------------------------
        # Data intervento
        # ----------------------------------------------------

        if not data_intervento:
            data_intervento = _now()

        # ----------------------------------------------------
        # INSERT SEMPRE NUOVO
        # ----------------------------------------------------

        dati = {
            "ticket_id": ticket_id,
            "tecnico": tecnico,
            "descrizione": descrizione,
            "stato": stato,
            "data_intervento": data_intervento,
        }

        risposta = (
            supabase.table("ticket_interventi")
            .insert(dati)
            .execute()
        )

        intervento = (
            risposta.data[0]
            if risposta.data
            else None
        )

        if not intervento:
            st.error(
                "Intervento non restituito da Supabase."
            )
            return None

        # ----------------------------------------------------
        # Aggiornamento stato ticket
        # ----------------------------------------------------

        if stato == "Risolto":
            aggiorna_stato_ticket(
                ticket_id,
                "Risolto",
            )

        elif stato == "In Lavorazione":
            aggiorna_stato_ticket(
                ticket_id,
                "In Lavorazione",
            )

        elif stato == "Aperto":
            aggiorna_stato_ticket(
                ticket_id,
                "Aperto",
            )

        return intervento

    except Exception as e:
        st.error(
            f"Errore salvataggio intervento tecnico: {e}"
        )
        return None


# ============================================================
# FOTO INTERVENTO
# ============================================================

def salva_foto_intervento(intervento_id, ticket_id, file):
    """
    Salva una foto associata allo SPECIFICO intervento.

    Il percorso viene salvato nel campo foto_path.
    """

    if file is None:
        return None

    try:
        contenuto = file.getvalue()

        if len(contenuto) > MAX_FILE_SIZE_BYTES:
            st.error(
                f"La foto supera il limite massimo di "
                f"{MAX_FILE_SIZE_MB} MB."
            )
            return None

        nome_originale = getattr(
            file,
            "name",
            "foto_intervento.jpg",
        )

        nome_file = sanitizza_nome_file(nome_originale)

        # Aggiunge ID intervento per evitare collisioni
        percorso = (
            f"ticket_{ticket_id}/"
            f"intervento_{intervento_id}/"
            f"{nome_file}"
        )

        content_type = getattr(
            file,
            "type",
            "image/jpeg",
        )

        supabase.storage.from_(BUCKET_ALLEGATI).upload(
            percorso,
            contenuto,
            {
                "content-type": content_type,
                "upsert": "true",
            },
        )

        (
            supabase.table("ticket_interventi")
            .update(
                {
                    "foto_path": percorso,
                }
            )
            .eq("id", intervento_id)
            .execute()
        )

        return percorso

    except Exception as e:
        st.error(
            f"Errore salvataggio foto intervento: {e}"
        )
        return None


def scarica_foto_intervento(foto_path):
    if not foto_path:
        return None

    try:
        return (
            supabase.storage
            .from_(BUCKET_ALLEGATI)
            .download(foto_path)
        )

    except Exception as e:
        st.error(
            f"Errore download foto intervento: {e}"
        )
        return None


# ============================================================
# FIRMA INTERVENTO
# ============================================================

def salva_firma_intervento(
    intervento_id,
    ticket_id,
    firma_bytes,
):
    """
    Salva la firma grafica associata allo specifico intervento.
    """

    if not firma_bytes:
        return None

    try:
        nome_file = (
            f"firma_intervento_{intervento_id}.png"
        )

        percorso = (
            f"firme/{ticket_id}/{nome_file}"
        )

        supabase.storage.from_(BUCKET_ALLEGATI).upload(
            percorso,
            firma_bytes,
            {
                "content-type": "image/png",
                "upsert": "true",
            },
        )

        (
            supabase.table("ticket_interventi")
            .update(
                {
                    "firma_path": percorso,
                }
            )
            .eq("id", intervento_id)
            .execute()
        )

        return percorso

    except Exception as e:
        st.error(
            f"Errore salvataggio firma intervento: {e}"
        )
        return None


def scarica_firma_intervento(firma_path):
    if not firma_path:
        return None

    try:
        return (
            supabase.storage
            .from_(BUCKET_ALLEGATI)
            .download(firma_path)
        )

    except Exception as e:
        st.error(
            f"Errore download firma intervento: {e}"
        )
        return None


# ============================================================
# CANCELLAZIONE TICKET
# ============================================================

def elimina_ticket_completo(ticket_id):
    """
    Elimina ticket, allegati e interventi.

    Gli eventuali file presenti nello Storage vengono
    eliminati prima della cancellazione delle relative righe.
    """

    try:
        # ----------------------------------------------------
        # 1. Allegati ticket
        # ----------------------------------------------------

        allegati = get_allegati(ticket_id)

        for allegato in allegati:
            percorso = allegato.get("percorso_file")

            if percorso:
                try:
                    supabase.storage.from_(
                        BUCKET_ALLEGATI
                    ).remove([percorso])
                except Exception:
                    pass

        # ----------------------------------------------------
        # 2. Foto e firme degli interventi
        # ----------------------------------------------------

        interventi = get_interventi(ticket_id)

        for intervento in interventi:

            foto_path = intervento.get("foto_path")

            if foto_path:
                try:
                    supabase.storage.from_(
                        BUCKET_ALLEGATI
                    ).remove([foto_path])
                except Exception:
                    pass

            firma_path = intervento.get("firma_path")

            if firma_path:
                try:
                    supabase.storage.from_(
                        BUCKET_ALLEGATI
                    ).remove([firma_path])
                except Exception:
                    pass

        # ----------------------------------------------------
        # 3. Elimina righe interventi
        # ----------------------------------------------------

        (
            supabase.table("ticket_interventi")
            .delete()
            .eq("ticket_id", ticket_id)
            .execute()
        )

        # ----------------------------------------------------
        # 4. Elimina righe allegati
        # ----------------------------------------------------

        (
            supabase.table("ticket_allegati")
            .delete()
            .eq("ticket_id", ticket_id)
            .execute()
        )

        # ----------------------------------------------------
        # 5. Elimina ticket
        # ----------------------------------------------------

        (
            supabase.table("tickets")
            .delete()
            .eq("id", ticket_id)
            .execute()
        )

        return True

    except Exception as e:
        st.error(
            f"Errore eliminazione ticket: {e}"
        )
        return False
