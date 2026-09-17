import re
from datetime import datetime
import streamlit as st
from supabase import create_client, Client

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
STATI = ["Aperto", "In Lavorazione", "Risolto", "Chiuso"]
PRIORITA = ["Bassa", "Media", "Alta", "Urgente"]
BUCKET_ALLEGATI = "allegati"


@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


supabase = get_supabase()


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
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


def get_tickets(limit=500):
    res = (
        supabase.table("tickets")
        .select("*")
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def get_ticket(ticket_id):
    res = (
        supabase.table("tickets")
        .select("*")
        .eq("id", ticket_id)
        .maybe_single()
        .execute()
    )
    return res.data


def get_tickets_tecnico(username, limit=500):
    res = (
        supabase.table("tickets")
        .select("*")
        .eq("assegnato_a", username)
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def get_tecnici_attivi():
    res = (
        supabase.table("utenti")
        .select("username, ruolo, attivo")
        .order("username")
        .execute()
    )
    rows = res.data or []
    return [
        r["username"]
        for r in rows
        if str(r.get("ruolo", "")).strip().lower() in {"tecnico", "technician"}
        and r.get("attivo", True) is not False
    ]


def get_utenti():
    return (
        supabase.table("utenti")
        .select("username, ruolo, attivo")
        .order("username")
        .execute()
        .data
        or []
    )


def get_utente(username):
    try:
        risposta = (
            supabase.table("utenti")
            .select("*")
            .eq("username", username)
            .maybe_single()
            .execute()
        )

        if risposta is None:
            return None

        return getattr(risposta, "data", None)

    except Exception as e:
        st.error(f"Errore caricamento utente: {e}")
        return None


def crea_utente(username, password_hash, ruolo, attivo=True):
    return (
        supabase.table("utenti")
        .insert({
            "username": username,
            "password": password_hash,
            "ruolo": ruolo,
            "attivo": attivo,
        })
        .execute()
    )


def aggiorna_utente(username, **fields):
    return (
        supabase.table("utenti")
        .update(fields)
        .eq("username", username)
        .execute()
    )


def get_categorie():
    return (
        supabase.table("categorie")
        .select("*")
        .order("nome")
        .execute()
        .data
        or []
    )


def get_nomi_categorie_attive():
    return [
        r["nome"] for r in get_categorie()
        if r.get("attivo", True) is not False
    ]


def aggiungi_categoria(nome):
    nome = str(nome or "").strip()
    if not nome:
        return False, "Nome categoria obbligatorio."
    try:
        supabase.table("categorie").insert({"nome": nome, "attivo": True}).execute()
        return True, "Categoria aggiunta."
    except Exception as e:
        return False, str(e)


def modifica_categoria(categoria_id, nuovo_nome):
    nuovo_nome = str(nuovo_nome or "").strip()
    if not nuovo_nome:
        return False, "Nome categoria obbligatorio."
    try:
        old = (
            supabase.table("categorie")
            .select("nome")
            .eq("id", categoria_id)
            .single()
            .execute()
            .data
        )
        old_name = old["nome"]
        supabase.table("categorie").update({"nome": nuovo_nome}).eq("id", categoria_id).execute()
        supabase.table("tickets").update({"categoria": nuovo_nome}).eq("categoria", old_name).execute()
        return True, "Categoria modificata."
    except Exception as e:
        return False, str(e)


def cambia_stato_categoria(categoria_id, attiva):
    try:
        supabase.table("categorie").update({"attivo": bool(attiva)}).eq("id", categoria_id).execute()
        return True, "Stato categoria aggiornato."
    except Exception as e:
        return False, str(e)


def registra_evento(ticket_id, utente, azione, dettagli=None):
    """Registra un evento nello storico/audit del ticket.
    Se la tabella audit_log non è ancora disponibile, l'operazione non
    blocca il normale funzionamento dell'app.
    """
    try:
        supabase.table("audit_log").insert({
            "ticket_id": ticket_id,
            "utente": utente,
            "azione": azione,
            "dettagli": dettagli,
        }).execute()
        return True
    except Exception:
        return False


def get_audit_log(ticket_id):
    """Restituisce lo storico audit del ticket in ordine cronologico."""
    try:
        risposta = (
            supabase.table("audit_log")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("data_evento", desc=False)
            .order("id", desc=False)
            .execute()
        )
        return risposta.data or []
    except Exception as e:
        st.error(f"Errore caricamento storico ticket: {e}")
        return []


def crea_ticket(titolo, descrizione, categoria, priorita, assegnato_a, creato_da):
    payload = {
        "titolo": titolo,
        "descrizione": descrizione,
        "categoria": categoria,
        "priorita": priorita,
        "assegnato_a": assegnato_a,
        "stato": "Aperto",
        "creato_da": creato_da,
    }
    ticket = supabase.table("tickets").insert(payload).execute().data[0]
    registra_evento(
        ticket["id"],
        creato_da,
        "Ticket creato",
        f"Ticket creato e assegnato a {assegnato_a}.",
    )
    return ticket


def aggiorna_stato_ticket(ticket_id, nuovo_stato):
    return (
        supabase.table("tickets")
        .update({
            "stato": nuovo_stato,
        })
        .eq("id", ticket_id)
        .execute()
    )


def chiudi_ticket(ticket_id, chiuso_da):
    risultato = (
        supabase.table("tickets")
        .update({
            "stato": "Chiuso",
            "data_chiusura": _now(),
            "chiuso_da": chiuso_da,
        })
        .eq("id", ticket_id)
        .execute()
    )
    registra_evento(
        ticket_id,
        chiuso_da,
        "Ticket chiuso",
        "Il ticket è stato chiuso dall'amministratore.",
    )
    return risultato


def salva_allegato(ticket_id, uploaded_file):
    if uploaded_file is None:
        return None

    content = uploaded_file.getvalue()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Il file supera il limite di {MAX_FILE_SIZE_MB} MB.")

    filename = sanitizza_nome_file(uploaded_file.name)
    path = f"ticket_{ticket_id}/{filename}"

    supabase.storage.from_(BUCKET_ALLEGATI).upload(
        path,
        content,
        {"content-type": uploaded_file.type or "application/octet-stream", "upsert": "true"},
    )

    supabase.table("ticket_allegati").insert({
        "ticket_id": ticket_id,
        "nome_file": filename,
        "percorso_file": path,
        "tipo_file": uploaded_file.type or "application/octet-stream",
    }).execute()

    return path


def get_allegati(ticket_id):
    return (
        supabase.table("ticket_allegati")
        .select("*")
        .eq("ticket_id", ticket_id)
        .order("data_caricamento", desc=True)
        .execute()
        .data
        or []
    )


def scarica_allegato(path):
    return supabase.storage.from_(BUCKET_ALLEGATI).download(path)


def get_interventi(ticket_id):
    """Restituisce tutti gli interventi del ticket in ordine cronologico."""
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
    """Compatibilità: restituisce l'ultimo intervento del ticket."""
    interventi = get_interventi(ticket_id)
    return interventi[-1] if interventi else None


def get_intervento_by_id(intervento_id):
    try:
        risposta = (
            supabase.table("ticket_interventi")
            .select("*")
            .eq("id", intervento_id)
            .maybe_single()
            .execute()
        )
        return risposta.data
    except Exception as e:
        st.error(f"Errore caricamento intervento: {e}")
        return None


def salva_intervento_tecnico(
    ticket_id,
    tecnico,
    descrizione_intervento,
    nuovo_stato,
    firma_path=None,
):
    """Crea SEMPRE un nuovo record di intervento."""
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise ValueError("Ticket non trovato.")

    if str(ticket.get("assegnato_a", "")).strip() != str(tecnico).strip():
        raise PermissionError("Il tecnico può intervenire solo sui ticket a lui assegnati.")

    if ticket.get("stato") in {"Risolto", "Chiuso"}:
        raise PermissionError("Un ticket risolto o chiuso non può essere modificato dal tecnico.")

    if nuovo_stato not in {"Aperto", "In Lavorazione", "Risolto"}:
        raise ValueError("Stato non consentito al tecnico.")

    descrizione = (descrizione_intervento or "").strip()
    if not descrizione:
        raise ValueError("La descrizione dell'intervento è obbligatoria.")

    stato_intervento = "Risolto" if nuovo_stato == "Risolto" else nuovo_stato

    dati = {
        "ticket_id": ticket_id,
        "tecnico": tecnico,
        "descrizione": descrizione,
        "stato": stato_intervento,
        "data_intervento": datetime.now().isoformat(),
    }
    if firma_path:
        dati["firma_path"] = firma_path

    risposta = supabase.table("ticket_interventi").insert(dati).execute()
    intervento = risposta.data[0] if risposta.data else None
    if not intervento:
        raise ValueError("Intervento non restituito da Supabase.")

    # Aggiorna anche lo stato principale del ticket e verifica il risultato.
    risultato = (
        supabase.table("tickets")
        .update({"stato": nuovo_stato})
        .eq("id", ticket_id)
        .eq("assegnato_a", tecnico)
        .select("id, stato")
        .execute()
    )

    if not risultato.data:
        raise RuntimeError(
            "L'intervento è stato registrato, ma lo stato del ticket non è stato aggiornato. "
            "Verificare i permessi di aggiornamento della tabella tickets in Supabase."
        )

    stato_salvato = risultato.data[0].get("stato")
    if stato_salvato != nuovo_stato:
        raise RuntimeError(
            f"Stato ticket non aggiornato correttamente: atteso '{nuovo_stato}', "
            f"ottenuto '{stato_salvato}'."
        )

    registra_evento(
        ticket_id,
        tecnico,
        "Intervento registrato",
        f"Intervento #{intervento.get('id')} registrato. Stato ticket: {nuovo_stato}.",
    )

    return intervento


def salva_foto_intervento(intervento_id, ticket_id, file, filename=None):
    if file is None:
        return None
    content = file.getvalue() if hasattr(file, "getvalue") else file
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"La foto supera il limite di {MAX_FILE_SIZE_MB} MB.")
    original_name = filename or getattr(file, "name", "foto_intervento.jpg")
    safe_name = sanitizza_nome_file(original_name)
    path = f"ticket_{ticket_id}/intervento_{intervento_id}/{safe_name}"
    content_type = getattr(file, "type", None) or "image/jpeg"
    supabase.storage.from_(BUCKET_ALLEGATI).upload(
        path, content, {"content-type": content_type, "upsert": "true"}
    )
    supabase.table("ticket_interventi").update({"foto_path": path}).eq("id", intervento_id).execute()
    return path


def scarica_foto_intervento(path):
    if not path:
        return None
    try:
        return supabase.storage.from_(BUCKET_ALLEGATI).download(path)
    except Exception:
        return None


def salva_firma_intervento(intervento_id, ticket_id, file_bytes, filename="firma.png"):
    if not file_bytes:
        raise ValueError("Firma non valida.")
    safe_name = sanitizza_nome_file(filename)
    path = f"firme/{ticket_id}/intervento_{intervento_id}/{safe_name}"
    supabase.storage.from_(BUCKET_ALLEGATI).upload(
        path, file_bytes, {"content-type": "image/png", "upsert": "true"}
    )
    supabase.table("ticket_interventi").update({"firma_path": path}).eq("id", intervento_id).execute()
    return path


def scarica_firma_intervento(path):
    try:
        return supabase.storage.from_(BUCKET_ALLEGATI).download(path)
    except Exception:
        return None


def elimina_ticket_completo(ticket_id):
    try:
        allegati = get_allegati(ticket_id)
        for a in allegati:
            path = a.get("percorso_file")
            if path:
                try:
                    supabase.storage.from_(BUCKET_ALLEGATI).remove([path])
                except Exception:
                    pass

        for intervento in get_interventi(ticket_id):
            for field in ("foto_path", "firma_path"):
                path = intervento.get(field)
                if path:
                    try:
                        supabase.storage.from_(BUCKET_ALLEGATI).remove([path])
                    except Exception:
                        pass

        supabase.table("ticket_allegati").delete().eq("ticket_id", ticket_id).execute()
        supabase.table("ticket_messaggi").delete().eq("ticket_id", ticket_id).execute()
        supabase.table("ticket_interventi").delete().eq("ticket_id", ticket_id).execute()
        try:
            supabase.table("audit_log").delete().eq("ticket_id", ticket_id).execute()
        except Exception:
            pass
        supabase.table("tickets").delete().eq("id", ticket_id).execute()
        return True
    except Exception as e:
        st.error(f"Errore eliminazione ticket: {e}")
        return False


def elimina_allegato(allegato_id, path):
    try:
        supabase.storage.from_(BUCKET_ALLEGATI).remove([path])
    finally:
        supabase.table("ticket_allegati").delete().eq("id", allegato_id).execute()

# ============================================================
# FIRMA AMMINISTRATORE
# ============================================================

def _percorso_firma_amministratore(username):
    username = sanitizza_nome_file(username or "amministratore")
    return f"firme/amministratori/{username}.png"


def salva_firma_amministratore(username, file_bytes):
    """Salva/sostituisce la firma dell'amministratore nello Storage."""
    if not username:
        raise ValueError("Amministratore non specificato.")
    if not file_bytes:
        raise ValueError("File firma non valido.")

    path = _percorso_firma_amministratore(username)
    supabase.storage.from_(BUCKET_ALLEGATI).upload(
        path,
        file_bytes,
        {"content-type": "image/png", "upsert": "true"},
    )
    return path


def scarica_firma_amministratore(username):
    """Recupera la firma associata all'amministratore indicato."""
    if not username:
        return None
    try:
        path = _percorso_firma_amministratore(username)
        return supabase.storage.from_(BUCKET_ALLEGATI).download(path)
    except Exception:
        return None
