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
    return (
        supabase.table("utenti")
        .select("*")
        .eq("username", username)
        .maybe_single()
        .execute()
        .data
    )


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
    return supabase.table("tickets").insert(payload).execute().data[0]


def aggiorna_stato_ticket(ticket_id, nuovo_stato):
    return (
        supabase.table("tickets")
        .update({"stato": nuovo_stato})
        .eq("id", ticket_id)
        .execute()
    )


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


def get_intervento(ticket_id):
    try:
        risposta = (
            supabase.table("ticket_interventi")
            .select("*")
            .eq("ticket_id", ticket_id)
            .execute()
        )
        return risposta.data[0] if risposta.data else None
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
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise ValueError("Ticket non trovato.")

    if str(ticket.get("assegnato_a", "")).strip() != str(tecnico).strip():
        raise PermissionError(
            "Il tecnico può intervenire solo sui ticket a lui assegnati."
        )

    if ticket.get("stato") in {"Risolto", "Chiuso"}:
        raise PermissionError(
            "Un ticket risolto o chiuso non può essere modificato dal tecnico."
        )

    if nuovo_stato not in {"Aperto", "In Lavorazione", "Risolto"}:
        raise ValueError("Stato non consentito al tecnico.")

    stato_intervento = (
        "In lavorazione" if nuovo_stato == "In Lavorazione" else nuovo_stato
    )

    dati = {
        "ticket_id": ticket_id,
        "tecnico": tecnico,
        "descrizione": (descrizione_intervento or "").strip(),
        "stato": stato_intervento,
        "data_intervento": datetime.now().isoformat(),
        "firma_path": firma_path,
    }

    esistente = get_intervento(ticket_id)
    if esistente:
        supabase.table("ticket_interventi").update(dati).eq(
            "ticket_id", ticket_id
        ).execute()
    else:
        supabase.table("ticket_interventi").insert(dati).execute()

    return aggiorna_stato_ticket(ticket_id, nuovo_stato)


def salva_firma_intervento(ticket_id, file_bytes, filename="firma.png"):
    filename = sanitizza_nome_file(filename)
    path = f"firme/{ticket_id}/{filename}"

    supabase.storage.from_(BUCKET_ALLEGATI).upload(
        path,
        file_bytes,
        {"content-type": "image/png", "upsert": "true"},
    )

    supabase.table("ticket_interventi").update({
        "firma_path": path,
    }).eq("ticket_id", ticket_id).execute()

    return path


def scarica_firma_intervento(path):
    return supabase.storage.from_(BUCKET_ALLEGATI).download(path)


def elimina_ticket_completo(ticket_id):
    allegati = get_allegati(ticket_id)
    for a in allegati:
        try:
            supabase.storage.from_(BUCKET_ALLEGATI).remove([a["percorso_file"]])
        except Exception:
            pass

    intervento = get_intervento(ticket_id)
    if intervento and intervento.get("firma_path"):
        try:
            supabase.storage.from_(BUCKET_ALLEGATI).remove([intervento["firma_path"]])
        except Exception:
            pass

    supabase.table("ticket_allegati").delete().eq("ticket_id", ticket_id).execute()
    supabase.table("ticket_messaggi").delete().eq("ticket_id", ticket_id).execute()
    supabase.table("ticket_interventi").delete().eq("ticket_id", ticket_id).execute()
    supabase.table("tickets").delete().eq("id", ticket_id).execute()


def elimina_allegato(allegato_id, path):
    try:
        supabase.storage.from_(BUCKET_ALLEGATI).remove([path])
    finally:
        supabase.table("ticket_allegati").delete().eq("id", allegato_id).execute()
