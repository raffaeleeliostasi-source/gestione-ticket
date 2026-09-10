import re
from datetime import datetime
import streamlit as st
from supabase import create_client, Client

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

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

def sanitizza_nome_file(nome_file):
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', nome_file)

def format_data(data):
    if not data:
        return ""
    try:
        return str(data).replace("T", " ")[:19]
    except Exception:
        return str(data)

def get_tickets(limit=200):
    try:
        risposta = supabase.table("tickets").select("*").order("id", desc=True).limit(limit).execute()
        return risposta.data or []
    except Exception as e:
        st.error(f"Errore caricamento ticket: {e}")
        return []

def get_ticket(ticket_id):
    try:
        risposta = supabase.table("tickets").select("*").eq("id", ticket_id).execute()
        return risposta.data[0] if risposta.data else None
    except Exception as e:
        st.error(f"Errore caricamento ticket: {e}")
        return None

def get_tecnici_attivi():
    try:
        risposta = supabase.table("utenti").select("*").order("username").execute()
        utenti = risposta.data or []
        return [
            u.get("username", "") for u in utenti
            if u.get("username") and u.get("attivo", True) is not False
            and str(u.get("ruolo", "")).strip().lower() == "tecnico"
        ]
    except Exception as e:
        st.error(f"Errore caricamento tecnici: {e}")
        return []

def get_categorie(solo_attive=True):
    try:
        query = supabase.table("categorie").select("*").order("nome")
        if solo_attive:
            query = query.eq("attivo", True)
        risposta = query.execute()
        return risposta.data or []
    except Exception as e:
        st.error(f"Errore caricamento categorie: {e}")
        return []

def get_nomi_categorie_attive():
    categorie = get_categorie(solo_attive=True)
    return [c.get("nome", "") for c in categorie]

def aggiungi_categoria(nome):
    try:
        nome = nome.strip()
        if not nome:
            return False, "Inserisci il nome della categoria."
        supabase.table("categorie").insert({"nome": nome, "attivo": True}).execute()
        return True, "Categoria aggiunta correttamente."
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            return False, "Esiste già una categoria con questo nome."
        return False, f"Errore: {e}"

def modifica_categoria(categoria_id, vecchio_nome, nuovo_nome):
    try:
        nuovo_nome = nuovo_nome.strip()
        if not nuovo_nome:
            return False, "Il nome della categoria non può essere vuoto."
        if nuovo_nome == vecchio_nome:
            return False, "Il nuovo nome è uguale a quello attuale."

        supabase.table("categorie").update({"nome": nuovo_nome}).eq("id", categoria_id).execute()
        supabase.table("tickets").update({"categoria": nuovo_nome}).eq("categoria", vecchio_nome).execute()
        return True, "Categoria modificata e ticket aggiornati."
    except Exception as e:
        return False, f"Errore: {e}"

def cambia_stato_categoria(categoria_id, attivo):
    try:
        supabase.table("categorie").update({"attivo": attivo}).eq("id", categoria_id).execute()
        return True, "Stato categoria aggiornato."
    except Exception as e:
        return False, f"Errore: {e}"

def get_allegati(ticket_id):
    try:
        risposta = supabase.table("ticket_allegati").select("*").eq("ticket_id", ticket_id).order("data_caricamento", desc=True).execute()
        return risposta.data or []
    except Exception as e:
        st.error(f"Errore caricamento allegati: {e}")
        return []

def salva_allegato(ticket_id, file):
    try:
        contenuto = file.getvalue()
        if len(contenuto) > MAX_FILE_SIZE_BYTES:
            st.warning(f"⚠️ Il file '{file.name}' supera il limite di {MAX_FILE_SIZE_MB}MB e non è stato salvato.")
            return

        nome_file_sicuro = sanitizza_nome_file(file.name)
        tipo_file = getattr(file, "type", "application/octet-stream")
        percorso_file = f"ticket_{ticket_id}/{nome_file_sicuro}"

        supabase.storage.from_("allegati").upload(
            path=percorso_file,
            file=contenuto,
            file_options={"content-type": tipo_file, "upsert": "true"}
        )

        supabase.table("ticket_allegati").insert({
            "ticket_id": ticket_id,
            "nome_file": nome_file_sicuro,
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

def get_intervento(ticket_id):
    try:
        risposta = supabase.table("ticket_interventi").select("*").eq("ticket_id", ticket_id).execute()
        return risposta.data[0] if risposta.data else None
    except Exception as e:
        st.error(f"Errore caricamento intervento: {e}")
        return None

def salva_intervento_tecnico(ticket_id, tecnico, descrizione_intervento, nuovo_stato, firma_path=None):
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
            supabase.table("ticket_interventi").update(dati).eq("ticket_id", ticket_id).execute()
        else:
            supabase.table("ticket_interventi").insert(dati).execute()

        supabase.table("tickets").update({"stato": nuovo_stato}).eq("id", ticket_id).execute()
        return True, "Intervento salvato correttamente."
    except Exception as e:
        return False, str(e)

def salva_firma_intervento(ticket_id, firma_png, tecnico):
    try:
        nome_file = f"firma_ticket_{ticket_id}_{tecnico}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        percorso = f"firme/{ticket_id}/{nome_file}"
        supabase.storage.from_("allegati").upload(percorso, firma_png, {"content-type": "image/png", "upsert": "true"})
        return True, percorso
    except Exception as e:
        return False, str(e)

def scarica_firma_intervento(percorso):
    try:
        return supabase.storage.from_("allegati").download(percorso)
    except Exception:
        return None

def elimina_ticket_completo(ticket_id):
    try:
        allegati = get_allegati(ticket_id)
        percorsi = [a.get("percorso_file") for a in allegati if a.get("percorso_file")]

        if percorsi:
            supabase.storage.from_("allegati").remove(percorsi)

        supabase.table("ticket_allegati").delete().eq("ticket_id", ticket_id).execute()
        supabase.table("ticket_messaggi").delete().eq("ticket_id", ticket_id).execute()
        supabase.table("ticket_interventi").delete().eq("ticket_id", ticket_id).execute()
        supabase.table("tickets").delete().eq("id", ticket_id).execute()
        return True, "Ticket eliminato completamente."
    except Exception as e:
        return False, str(e)
