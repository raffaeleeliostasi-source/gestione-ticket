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

# ============================================================
# SICUREZZA / AUTORIZZAZIONI
# ============================================================
RUOLI_AMMINISTRATIVI = {"amministratore", "admin"}
RUOLI_TECNICI = {"tecnico", "technician"}

def _utente_sessione():
    if not st.session_state.get("logged_in"):
        raise PermissionError("Sessione non autenticata.")
    username=str(st.session_state.get("username") or "").strip()
    if not username: raise PermissionError("Utente di sessione non valido.")
    utente=get_utente(username)
    if not utente: raise PermissionError("Utente non trovato.")
    if utente.get("attivo",True) is False: raise PermissionError("L'account non è attivo.")
    return utente

def _is_admin(utente):
    return str(utente.get("ruolo","")).strip().lower() in RUOLI_AMMINISTRATIVI

def _require_admin():
    utente=_utente_sessione()
    if not _is_admin(utente): raise PermissionError("Operazione riservata agli amministratori.")
    return utente

def _require_ticket_access(ticket_id, allow_creator=True):
    utente=_utente_sessione(); username=str(utente.get("username") or "").strip()
    ticket=get_ticket(ticket_id)
    if not ticket: raise ValueError("Ticket non trovato.")
    if _is_admin(utente): return utente,ticket
    tecnici={str(x).strip() for x in (ticket.get("tecnici_assegnati") or get_ticket_tecnici(ticket_id)) if str(x).strip()}
    creatore=str(ticket.get("creato_da") or "").strip()
    if username in tecnici or (allow_creator and username==creatore): return utente,ticket
    raise PermissionError("Accesso non autorizzato a questo ticket.")

def _require_technician_on_ticket(ticket_id):
    utente,ticket=_require_ticket_access(ticket_id,allow_creator=False)
    if _is_admin(utente): raise PermissionError("L'operazione è riservata al tecnico assegnato.")
    if str(utente.get("ruolo","")).strip().lower() not in RUOLI_TECNICI: raise PermissionError("Operazione riservata ai tecnici.")
    return utente,ticket

def _ticket_id_da_path(path):
    # I percorsi degli allegati/foto iniziano con ticket_<id>,
    # mentre le firme tecniche sono salvate come firme/<id>/... .
    valore = str(path or "").strip()
    m = re.match(r"^(?:ticket_(\d+)|firme/(\d+))(?:/|$)", valore)
    if not m:
        return None
    return int(m.group(1) or m.group(2))



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
    ticket = getattr(res, "data", None)
    if not ticket:
        return ticket

    tecnici = get_ticket_tecnici(ticket_id)
    if not tecnici and ticket.get("assegnato_a"):
        tecnici = [str(ticket.get("assegnato_a")).strip()]
    ticket["tecnici_assegnati"] = tecnici
    if tecnici:
        ticket["assegnato_a"] = tecnici[0]
    return ticket


def get_ticket_tecnici(ticket_id):
    try:
        risposta = (
            supabase.table("ticket_tecnici")
            .select("tecnico")
            .eq("ticket_id", ticket_id)
            .order("id")
            .execute()
        )
        return [
            str(r.get("tecnico", "")).strip()
            for r in (risposta.data or [])
            if str(r.get("tecnico", "")).strip()
        ]
    except Exception as e:
        st.error(f"Errore caricamento tecnici del ticket: {e}")
        return []


def assegna_tecnici_ticket(ticket_id,tecnici):
    _require_admin(); return _assegna_tecnici_ticket(ticket_id,tecnici)

def _assegna_tecnici_ticket(ticket_id,tecnici):
    tecnici_puliti=[]
    for tecnico in tecnici or []:
        valore=str(tecnico or "").strip()
        if valore and valore not in tecnici_puliti: tecnici_puliti.append(valore)
    if not tecnici_puliti: raise ValueError("È necessario assegnare almeno un tecnico al ticket.")
    rows=supabase.table("utenti").select("username,ruolo,attivo").in_("username",tecnici_puliti).execute().data or []
    validi={str(r.get("username") or "").strip() for r in rows if str(r.get("ruolo","")).strip().lower() in RUOLI_TECNICI and r.get("attivo",True) is not False}
    mancanti=[x for x in tecnici_puliti if x not in validi]
    if mancanti: raise ValueError("Tecnico non valido, inesistente o disattivato: "+", ".join(mancanti))
    supabase.table("ticket_tecnici").delete().eq("ticket_id",ticket_id).execute()
    supabase.table("ticket_tecnici").insert([{"ticket_id":ticket_id,"tecnico":x} for x in tecnici_puliti]).execute()
    return tecnici_puliti

def get_tickets_tecnico(username, limit=500):
    username = str(username or "").strip()
    if not username:
        return []

    try:
        assegnazioni = (
            supabase.table("ticket_tecnici")
            .select("ticket_id")
            .eq("tecnico", username)
            .execute()
        )
        ticket_ids = [r.get("ticket_id") for r in (assegnazioni.data or []) if r.get("ticket_id") is not None]

        if ticket_ids:
            res = (
                supabase.table("tickets")
                .select("*")
                .in_("id", ticket_ids)
                .order("id", desc=True)
                .limit(limit)
                .execute()
            )
            tickets = res.data or []
        else:
            # Compatibilità con eventuali ticket creati prima dell'introduzione
            # della tabella ticket_tecnici.
            res = (
                supabase.table("tickets")
                .select("*")
                .eq("assegnato_a", username)
                .order("id", desc=True)
                .limit(limit)
                .execute()
            )
            tickets = res.data or []

        for ticket in tickets:
            tecnici = get_ticket_tecnici(ticket.get("id"))
            if not tecnici and ticket.get("assegnato_a"):
                tecnici = [str(ticket.get("assegnato_a")).strip()]
            ticket["tecnici_assegnati"] = tecnici
            if tecnici:
                ticket["assegnato_a"] = tecnici[0]

        return tickets
    except Exception as e:
        st.error(f"Errore caricamento ticket del tecnico: {e}")
        return []

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
        .select("nome, cognome, username, ruolo, attivo")
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


def crea_utente(username,password_hash,ruolo,attivo=True,nome="",cognome=""):
    _require_admin()
    username=str(username or "").strip().lower(); ruolo=str(ruolo or "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,49}",username): raise ValueError("Username non valido.")
    if ruolo.lower() not in {"tecnico","amministratore","admin","technician"}: raise ValueError("Ruolo non valido.")
    return supabase.table("utenti").insert({"nome":str(nome or "").strip()[:100],"cognome":str(cognome or "").strip()[:100],"username":username,"password":password_hash,"ruolo":ruolo,"attivo":bool(attivo)}).execute()

def aggiorna_utente(username,**fields):
    _require_admin(); username=str(username or "").strip()
    allowed={"nome","cognome","password","ruolo","attivo"}; unknown=set(fields)-allowed
    if unknown: raise ValueError("Campi utente non consentiti: "+", ".join(sorted(unknown)))
    if not fields: raise ValueError("Nessun dato da aggiornare.")
    if "ruolo" in fields:
        ruolo=str(fields["ruolo"] or "").strip()
        if ruolo.lower() not in {"tecnico","amministratore","admin","technician"}: raise ValueError("Ruolo non valido.")
        fields["ruolo"]=ruolo
    if "attivo" in fields: fields["attivo"]=bool(fields["attivo"])
    for k in ("nome","cognome"):
        if k in fields: fields[k]=str(fields[k] or "").strip()[:100]
    return supabase.table("utenti").update(fields).eq("username",username).execute()

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
    _require_admin(); nome=str(nome or "").strip()
    if not nome or len(nome)>100: return False,"Nome categoria non valido."
    try:
        if nome.lower() in {str(x).strip().lower() for x in get_nomi_categorie_attive()}: return False,"Categoria già esistente."
        supabase.table("categorie").insert({"nome":nome,"attivo":True}).execute(); return True,"Categoria aggiunta."
    except Exception: return False,"Errore durante l'aggiunta della categoria."

def modifica_categoria(categoria_id,nuovo_nome):
    _require_admin(); nuovo_nome=str(nuovo_nome or "").strip()
    if not nuovo_nome or len(nuovo_nome)>100: return False,"Nome categoria non valido."
    try:
        old=supabase.table("categorie").select("nome").eq("id",categoria_id).single().execute().data
        old_name=old["nome"]
        supabase.table("categorie").update({"nome":nuovo_nome}).eq("id",categoria_id).execute()
        supabase.table("tickets").update({"categoria":nuovo_nome}).eq("categoria",old_name).execute()
        return True,"Categoria modificata."
    except Exception: return False,"Errore durante la modifica della categoria."

def cambia_stato_categoria(categoria_id,attiva):
    _require_admin()
    try:
        supabase.table("categorie").update({"attivo":bool(attiva)}).eq("id",categoria_id).execute(); return True,"Stato categoria aggiornato."
    except Exception: return False,"Errore durante l'aggiornamento della categoria."

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


def crea_ticket(titolo,descrizione,categoria,priorita,tecnici=None,creato_da=None,assegnato_a=None):
    utente=_utente_sessione(); session_username=str(utente.get("username") or "").strip()
    creatore=str(creato_da or session_username).strip()
    if creatore!=session_username: raise PermissionError("Il creatore del ticket deve coincidere con l'utente autenticato.")
    titolo=str(titolo or "").strip(); descrizione=str(descrizione or "").strip(); categoria=str(categoria or "").strip(); priorita=str(priorita or "").strip()
    if not titolo or not descrizione: raise ValueError("Titolo e descrizione sono obbligatori.")
    if priorita not in PRIORITA: raise ValueError("Priorità non valida.")
    if categoria not in get_nomi_categorie_attive(): raise ValueError("Categoria non valida o non attiva.")
    if tecnici is None: tecnici=[]
    elif isinstance(tecnici,str): tecnici=[tecnici]
    tecnici_puliti=[]
    for tecnico in tecnici:
        valore=str(tecnico or "").strip()
        if valore and valore not in tecnici_puliti: tecnici_puliti.append(valore)
    if not tecnici_puliti and assegnato_a: tecnici_puliti=[str(assegnato_a).strip()]
    if not tecnici_puliti: raise ValueError("È necessario assegnare almeno un tecnico al ticket.")
    payload={"titolo":titolo,"descrizione":descrizione,"categoria":categoria,"priorita":priorita,"assegnato_a":tecnici_puliti[0],"stato":"Aperto","creato_da":creatore}
    risposta=supabase.table("tickets").insert(payload).execute()
    if not risposta.data: raise ValueError("Ticket non restituito da Supabase.")
    ticket=risposta.data[0]; ticket_id=ticket["id"]
    _assegna_tecnici_ticket(ticket_id,tecnici_puliti); ticket["tecnici_assegnati"]=tecnici_puliti
    registra_evento(ticket_id,creatore,"Ticket creato",f"Ticket creato e assegnato ai tecnici: {', '.join(tecnici_puliti)}.")
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


def chiudi_ticket(ticket_id,chiuso_da):
    utente=_require_admin(); username=str(utente.get("username") or "").strip()
    if str(chiuso_da or "").strip()!=username: raise PermissionError("La chiusura deve essere eseguita dall'amministratore autenticato.")
    _,ticket=_require_ticket_access(ticket_id)
    if ticket.get("stato")=="Chiuso": return {"data":[ticket]}
    risultato=supabase.table("tickets").update({"stato":"Chiuso","data_chiusura":_now(),"chiuso_da":username}).eq("id",ticket_id).execute()
    registra_evento(ticket_id,username,"Ticket chiuso","Il ticket è stato chiuso dall'amministratore.")
    return risultato

def salva_allegato(ticket_id,uploaded_file):
    if uploaded_file is None: return None
    _require_ticket_access(ticket_id)
    content=uploaded_file.getvalue()
    if not content: raise ValueError("Il file è vuoto.")
    if len(content)>MAX_FILE_SIZE_BYTES: raise ValueError(f"Il file supera il limite di {MAX_FILE_SIZE_MB} MB.")
    filename=sanitizza_nome_file(uploaded_file.name); path=f"ticket_{int(ticket_id)}/{filename}"
    content_type=str(getattr(uploaded_file,"type",None) or "application/octet-stream").lower()
    supabase.storage.from_(BUCKET_ALLEGATI).upload(path,content,{"content-type":content_type,"upsert":"false"})
    supabase.table("ticket_allegati").insert({"ticket_id":ticket_id,"nome_file":filename,"percorso_file":path,"tipo_file":content_type}).execute()
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
    ticket_id=_ticket_id_da_path(path)
    if ticket_id is None: raise PermissionError("Percorso allegato non valido.")
    _require_ticket_access(ticket_id)
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


def salva_intervento_tecnico(ticket_id,tecnico,descrizione_intervento,nuovo_stato,firma_path=None):
    utente,ticket=_require_technician_on_ticket(ticket_id); session_username=str(utente.get("username") or "").strip()
    if str(tecnico or "").strip()!=session_username: raise PermissionError("Il tecnico dell'intervento deve coincidere con l'utente autenticato.")
    if ticket.get("stato") in {"Risolto","Chiuso"}: raise PermissionError("Un ticket risolto o chiuso non può essere modificato dal tecnico.")
    nuovo_stato=str(nuovo_stato or "").strip()
    if nuovo_stato not in {"Aperto","In Lavorazione","Risolto"}: raise ValueError("Stato non consentito al tecnico.")
    descrizione=str(descrizione_intervento or "").strip()
    if not descrizione: raise ValueError("La descrizione dell'intervento è obbligatoria.")
    if firma_path: raise ValueError("La firma viene associata solo tramite la funzione dedicata.")
    risposta=supabase.table("ticket_interventi").insert({"ticket_id":ticket_id,"tecnico":session_username,"descrizione":descrizione,"stato":nuovo_stato,"data_intervento":datetime.now().isoformat()}).execute()
    intervento=risposta.data[0] if risposta.data else None
    if not intervento: raise ValueError("Intervento non restituito da Supabase.")
    risultato=supabase.table("tickets").update({"stato":nuovo_stato}).eq("id",ticket_id).select("id,stato").execute()
    if not risultato.data or risultato.data[0].get("stato")!=nuovo_stato: raise RuntimeError("Lo stato del ticket non è stato aggiornato correttamente.")
    registra_evento(ticket_id,session_username,"Intervento registrato",f"Intervento #{intervento.get('id')} registrato. Stato ticket: {nuovo_stato}.")
    return intervento

def salva_foto_intervento(intervento_id,ticket_id,file,filename=None):
    if file is None: return None
    utente,_=_require_technician_on_ticket(ticket_id)
    intervento=get_intervento_by_id(intervento_id)
    if not intervento or int(intervento.get("ticket_id"))!=int(ticket_id): raise PermissionError("Intervento non valido per questo ticket.")
    if str(intervento.get("tecnico") or "").strip()!=str(utente.get("username") or "").strip(): raise PermissionError("Puoi allegare una foto solo al tuo intervento.")
    content=file.getvalue() if hasattr(file,"getvalue") else file
    if not content or len(content)>MAX_FILE_SIZE_BYTES: raise ValueError("Foto non valida o oltre il limite consentito.")
    content_type=str(getattr(file,"type",None) or "image/jpeg").lower()
    if content_type not in {"image/jpeg","image/png"}: raise ValueError("La foto deve essere in formato JPG o PNG.")
    safe_name=sanitizza_nome_file(filename or getattr(file,"name","foto_intervento.jpg")); path=f"ticket_{int(ticket_id)}/intervento_{int(intervento_id)}/{safe_name}"
    supabase.storage.from_(BUCKET_ALLEGATI).upload(path,content,{"content-type":content_type,"upsert":"false"})
    supabase.table("ticket_interventi").update({"foto_path":path}).eq("id",intervento_id).execute(); return path

def scarica_foto_intervento(path):
    if not path: return None
    ticket_id=_ticket_id_da_path(path)
    if ticket_id is None: return None
    _require_ticket_access(ticket_id)
    try: return supabase.storage.from_(BUCKET_ALLEGATI).download(path)
    except Exception: return None

def salva_firma_intervento(intervento_id,ticket_id,file_bytes,filename="firma.png"):
    if not file_bytes: raise ValueError("Firma non valida.")
    utente,_=_require_technician_on_ticket(ticket_id); intervento=get_intervento_by_id(intervento_id)
    if not intervento or int(intervento.get("ticket_id"))!=int(ticket_id): raise PermissionError("Intervento non valido per questo ticket.")
    if str(intervento.get("tecnico") or "").strip()!=str(utente.get("username") or "").strip(): raise PermissionError("Puoi firmare solo il tuo intervento.")
    if len(file_bytes)>MAX_FILE_SIZE_BYTES: raise ValueError("La firma supera il limite consentito.")
    path=f"firme/{int(ticket_id)}/intervento_{int(intervento_id)}/{sanitizza_nome_file(filename)}"
    supabase.storage.from_(BUCKET_ALLEGATI).upload(path,file_bytes,{"content-type":"image/png","upsert":"false"})
    supabase.table("ticket_interventi").update({"firma_path":path}).eq("id",intervento_id).execute(); return path

def scarica_firma_intervento(path):
    ticket_id=_ticket_id_da_path(path)
    if ticket_id is None: return None
    _require_ticket_access(ticket_id)
    try: return supabase.storage.from_(BUCKET_ALLEGATI).download(path)
    except Exception: return None

def elimina_ticket_completo(ticket_id):
    _require_admin(); _require_ticket_access(ticket_id)
    try:
        for a in get_allegati(ticket_id):
            path=a.get("percorso_file")
            if path:
                try: supabase.storage.from_(BUCKET_ALLEGATI).remove([path])
                except Exception: pass
        for intervento in get_interventi(ticket_id):
            for field in ("foto_path","firma_path"):
                path=intervento.get(field)
                if path:
                    try: supabase.storage.from_(BUCKET_ALLEGATI).remove([path])
                    except Exception: pass
        supabase.table("ticket_allegati").delete().eq("ticket_id",ticket_id).execute()
        supabase.table("ticket_messaggi").delete().eq("ticket_id",ticket_id).execute()
        supabase.table("ticket_interventi").delete().eq("ticket_id",ticket_id).execute()
        supabase.table("ticket_tecnici").delete().eq("ticket_id",ticket_id).execute()
        supabase.table("tickets").delete().eq("id",ticket_id).execute()
        try:
            supabase.table("audit_log").delete().eq("ticket_id",ticket_id).execute()
        except Exception:
            pass
        return True
    except Exception:
        st.error("Errore eliminazione ticket."); return False

def elimina_allegato(allegato_id,path):
    ticket_id=_ticket_id_da_path(path)
    if ticket_id is None: raise PermissionError("Percorso allegato non valido.")
    _require_ticket_access(ticket_id)
    try: supabase.storage.from_(BUCKET_ALLEGATI).remove([path])
    finally: supabase.table("ticket_allegati").delete().eq("id",allegato_id).eq("ticket_id",ticket_id).execute()

def _percorso_firma_amministratore(username):
    username = sanitizza_nome_file(username or "amministratore")
    return f"firme/amministratori/{username}.png"


def salva_firma_amministratore(username,file_bytes):
    utente=_require_admin(); session_username=str(utente.get("username") or "").strip()
    if str(username or "").strip()!=session_username: raise PermissionError("Puoi modificare solo la firma del tuo account amministratore.")
    if not file_bytes: raise ValueError("File firma non valido.")
    if len(file_bytes)>MAX_FILE_SIZE_BYTES: raise ValueError("La firma supera il limite consentito.")
    path=_percorso_firma_amministratore(session_username)
    supabase.storage.from_(BUCKET_ALLEGATI).upload(path,file_bytes,{"content-type":"image/png","upsert":"true"}); return path

def scarica_firma_amministratore(username):
    if not username: return None
    utente=_utente_sessione()
    if not _is_admin(utente): raise PermissionError("Operazione riservata agli amministratori.")
    path=_percorso_firma_amministratore(username)
    try: return supabase.storage.from_(BUCKET_ALLEGATI).download(path)
    except Exception: return None

