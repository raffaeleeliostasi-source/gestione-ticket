import hmac
from io import BytesIO
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import auth
import database as db
import pdf_generator

def is_admin():
    return st.session_state.get("ruolo", "").strip().lower() == "amministratore"

def pagina_login():
    st.title("🎫 Gestione Ticket")
    with st.form("form_login"):
        username = st.text_input("Username").strip().lower()
        password = st.text_input("Password", type="password")
        if st.form_submit_button("🔐 Accedi", use_container_width=True):
            if not username or not password:
                st.warning("Inserisci username e password.")
                return
            risposta = db.supabase.table("utenti").select("*").eq("username", username).execute()
            if not risposta.data or risposta.data[0].get("attivo") is False:
                st.error("❌ Credenziali errate o account disattivato.")
                return
            utente = risposta.data[0]
            if not auth.verifica_password(password, utente.get("password", "")):
                st.error("❌ Credenziali errate.")
                return
            if auth.password_da_migrare(utente.get("password", "")):
                db.supabase.table("utenti").update({"password": auth.genera_hash_password(password)}).eq("id", utente["id"]).execute()
            st.session_state.logged_in = True
            st.session_state.username = utente["username"]
            st.session_state.ruolo = utente.get("ruolo", "")
            st.rerun()

def pagina_nuovo_ticket():
    st.title("➕ Nuovo Ticket")
    categorie = db.get_nomi_categorie_attive()
    tecnici = db.get_tecnici_attivi()

    with st.form("nuovo_ticket_form"):
        titolo = st.text_input("Titolo del problema")
        descrizione = st.text_area("Descrizione", height=150)
        col1, col2 = st.columns(2)
        categoria = col1.selectbox("Categoria", categorie) if categorie else None
        priorita = col2.selectbox("Priorità", ["Bassa", "Media", "Alta", "Urgente"])
        assegnato_a = st.selectbox("👷 Assegna a", tecnici) if tecnici else None
        allegati = st.file_uploader("📁 Allegati", accept_multiple_files=True)
        foto = st.camera_input("📷 Scatta una foto")

        if st.form_submit_button("🎫 Crea Ticket", use_container_width=True):
            if not titolo or not descrizione or not categoria or not assegnato_a:
                st.warning("Compila tutti i campi obbligatori.")
                return
            res = db.supabase.table("tickets").insert({
                "titolo": titolo, "descrizione": descrizione, "categoria": categoria,
                "priorita": priorita, "assegnato_a": assegnato_a, "stato": "Aperto",
                "creato_da": st.session_state.username
            }).execute()
            if res.data:
                tid = res.data[0]["id"]
                if allegati:
                    for f in allegati: db.salva_allegato(tid, f)
                if foto:
                    db.salva_allegato(tid, foto)
                st.success("✅ Ticket creato con successo!")

def mostra_ticket(ticket):
    tid = ticket["id"]
    chiuso = ticket.get("stato") == "Chiuso"
    with st.expander(f"🎫 #{tid} - {ticket['titolo']} | {ticket.get('stato')}"):
        st.write(f"**Categoria:** {ticket.get('categoria')} | **Priorità:** {ticket.get('priorita')}")
        st.write(f"**Tecnico:** {ticket.get('assegnato_a')} | **Creato da:** {ticket.get('creato_da')}")
        st.write("### 📝 Descrizione", ticket.get("descrizione"))

        intervento = db.get_intervento(tid)
        if intervento:
            st.success(f"Intervento eseguito da {intervento.get('tecnico')}: {intervento.get('descrizione')}")

        if not is_admin() and ticket.get("assegnato_a") == st.session_state.username and not chiuso:
            st.subheader("🛠️ Registra Intervento")
            desc_int = st.text_area("Cosa hai fatto?", key=f"desc_{tid}")
            nuovo_stato = st.selectbox("Stato", ["In lavorazione", "Risolto"], key=f"st_{tid}")
            canvas = st_canvas(stroke_width=2, stroke_color="#000", height=150, width=400, key=f"canvas_{tid}")

            if st.button("💾 Salva intervento", key=f"btn_int_{tid}"):
                firma_path = None
                if canvas.image_data is not None and nuovo_stato == "Risolto":
                    img = Image.fromarray(canvas.image_data.astype("uint8"))
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    ok, firma_path = db.salva_firma_intervento(tid, buf.getvalue(), st.session_state.username)
                db.salva_intervento_tecnico(tid, st.session_state.username, desc_int, nuovo_stato, firma_path)
                st.rerun()

        if is_admin():
            col1, col2 = st.columns(2)
            pdf = pdf_generator.genera_pdf(ticket)
            col1.download_button("📄 Scarica PDF", pdf, file_name=f"ticket_{tid}.pdf", mime="application/pdf", key=f"pdf_{tid}")
            if col2.button("🗑️ Elimina", key=f"del_{tid}"):
                db.elimina_ticket_completo(tid)
                st.rerun()

def pagina_dashboard():
    st.title("🏠 Dashboard Ticket")
    
    tutti_i_tickets = db.get_tickets()
    if not tutti_i_tickets:
        st.info("Nessun ticket presente nel sistema.")
        return

    # Se l'utente è un Tecnico, filtra per mostrare i ticket assegnati a lui o creati da lui
    if not is_admin():
        utente_attuale = st.session_state.username.lower()
        tickets = [
            t for t in tutti_i_tickets 
            if str(t.get("assegnato_a", "")).lower() == utente_attuale 
            or str(t.get("creato_da", "")).lower() == utente_attuale
        ]
    else:
        tickets = tutti_i_tickets

    if not tickets:
        st.info("Non ci sono ticket assegnati a te o creati da te al momento.")
        return

    # --- BARRA DI RICERCA E FILTRI ---
    with st.expander("🔍 Filtri e Ricerca", expanded=True):
        col_search, col_stato, col_prio = st.columns([2, 1, 1])
        
        testo_ricerca = col_search.text_input("Cerca (Titolo, Descrizione, ID o Creatore)", "").lower()
        stato_selezionato = col_stato.selectbox("Stato", ["Tutti", "Aperto", "In lavorazione", "Risolto", "Chiuso"])
        priorita_selezionata = col_prio.selectbox("Priorità", ["Tutte", "Bassa", "Media", "Alta", "Urgente"])

    # --- LOGICA DI FILTRAGGIO ---
    tickets_filtrati = []
    for t in tickets:
        match_testo = (
            testo_ricerca in str(t.get("id", "")).lower() or
            testo_ricerca in t.get("titolo", "").lower() or
            testo_ricerca in t.get("descrizione", "").lower() or
            testo_ricerca in t.get("creato_da", "").lower()
        )
        
        match_stato = (stato_selezionato == "Tutti") or (t.get("stato") == stato_selezionato)
        match_prio = (priorita_selezionata == "Tutte") or (t.get("priorita") == priorita_selezionata)

        if match_testo and match_stato and match_prio:
            tickets_filtrati.append(t)

    # --- METRICHE RAPIDE ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Totale Visualizzati", len(tickets_filtrati))
    col2.metric("Aperti / In corso", len([t for t in tickets_filtrati if t.get("stato") in ["Aperto", "In lavorazione"]]))
    col3.metric("Risolti / Chiusi", len([t for t in tickets_filtrati if t.get("stato") in ["Risolto", "Chiuso"]]))

    st.divider()

    # --- LISTA TICKET ---
    if not tickets_filtrati:
        st.warning("Nessun ticket trovato con i criteri di ricerca selezionati.")
        return

    for t in tickets_filtrati:
        mostra_ticket(t)

def pagina_amministrazione():
    if not is_admin():
        st.error("Accesso riservato agli amministratori.")
        return

    st.title("👨‍💼 Pannello Amministrazione")
    tab_utenti, tab_cat = st.tabs(["👥 Gestione Utenti", "🏷️ Gestione Categorie"])

    # TAB UTENTI
    with tab_utenti:
        st.subheader("➕ Crea Nuovo Utente")
        with st.form("form_nuovo_utente"):
            new_user = st.text_input("Username").strip().lower()
            new_pass = st.text_input("Password", type="password")
            auth.mostra_regole_password()
            new_role = st.selectbox("Ruolo", ["Tecnico", "Amministratore"])

            if st.form_submit_button("➕ Aggiungi Utente"):
                err = auth.valida_password(new_pass)
                if err:
                    for e in err: st.error(e)
                elif not new_user:
                    st.warning("Inserisci uno username.")
                else:
                    try:
                        pass_hash = auth.genera_hash_password(new_pass)
                        db.supabase.table("utenti").insert({
                            "username": new_user,
                            "password": pass_hash,
                            "ruolo": new_role,
                            "attivo": True
                        }).execute()
                        st.success(f"Utente '{new_user}' creato correttamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore creazione utente: {e}")

        st.divider()
        st.subheader("📋 Lista Utenti")
        res = db.supabase.table("utenti").select("*").order("username").execute()
        utenti = res.data or []

        for u in utenti:
            uid = u["id"]
            uname = u["username"]
            attivo = u.get("attivo", True)
            ruolo = u.get("ruolo", "Tecnico")

            with st.expander(f"👤 {uname} ({ruolo}) - {'🟢 Attivo' if attivo else '🔴 Disattivato'}"):
                c1, c2, c3 = st.columns(3)
                nuovo_ruolo = c1.selectbox("Ruolo", ["Tecnico", "Amministratore"], index=0 if ruolo == "Tecnico" else 1, key=f"r_{uid}")
                stato_str = c2.selectbox("Stato", ["Attivo", "Disattivato"], index=0 if attivo else 1, key=f"s_{uid}")

                if c3.button("💾 Aggiorna", key=f"up_{uid}"):
                    db.supabase.table("utenti").update({
                        "ruolo": nuovo_ruolo,
                        "attivo": (stato_str == "Attivo")
                    }).eq("id", uid).execute()
                    st.success("Utente aggiornato!")
                    st.rerun()

                st.markdown("**Reset Password**")
                p1, p2 = st.columns([3, 1])
                reset_pass = p1.text_input("Nuova password", type="password", key=f"p_{uid}")
                if p2.button("🔑 Reset", key=f"res_{uid}"):
                    err = auth.valida_password(reset_pass)
                    if err:
                        for e in err: st.error(e)
                    else:
                        db.supabase.table("utenti").update({
                            "password": auth.genera_hash_password(reset_pass)
                        }).eq("id", uid).execute()
                        st.success("Password aggiornata!")

    # TAB CATEGORIE
    with tab_cat:
        st.subheader("➕ Nuova Categoria")
        c_i, c_b = st.columns([3, 1])
        nuova_cat = c_i.text_input("Nome Categoria")
        if c_b.button("➕ Aggiungi"):
            ok, msg = db.aggiungi_categoria(nuova_cat)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

        st.divider()
        st.subheader("📋 Categorie Esistenti")
        categorie = db.get_categorie(solo_attive=False)
        for cat in categorie:
            cid = cat["id"]
            cnome = cat["nome"]
            cattiva = cat.get("attivo", True)

            col_n, col_s, col_b = st.columns([2, 1, 1])
            nuovo_nome = col_n.text_input("Nome", value=cnome, key=f"cname_{cid}")
            stato_cat = col_s.selectbox("Stato", ["Attiva", "Disattivata"], index=0 if cattiva else 1, key=f"cs_{cid}")

            if col_b.button("💾 Salva", key=f"cbtn_{cid}"):
                if nuovo_nome != cnome:
                    db.modifica_categoria(cid, cnome, nuovo_nome)
                db.cambia_stato_categoria(cid, (stato_cat == "Attiva"))
                st.success("Categoria aggiornata!")
                st.rerun()
