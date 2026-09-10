import hmac
from io import BytesIO
import streamlit as st
import pandas as pd
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import auth
import database as db
import pdf_generator

def is_admin():
    ruolo = str(st.session_state.get("ruolo", "")).strip().lower()
    return ruolo in ["amministratore", "admin"]

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
import streamlit as st
from io import BytesIO
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import database as db
import pdf_generator

def mostra_dettaglio_ticket(ticket_id):
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        st.error("Ticket non trovato.")
        return

    st.subheader(f"Ticket #{ticket.get('id')} - {ticket.get('titolo', '')}")
    
    # Informazioni principali
    st.write(f"**Stato:** {ticket.get('stato', '')}")
    st.write(f"**Priorità:** {ticket.get('priorita', '')}")
    st.write(f"**Categoria:** {ticket.get('categoria', '')}")
    st.write(f"**Creato da:** {ticket.get('creato_da', '')}")
    st.write(f"**Tecnico Assegnato:** {ticket.get('assegnato_a', 'Nessuno')}")
    
    st.markdown("---")
    st.write(f"**Descrizione:**\n{ticket.get('descrizione', '')}")
    st.markdown("---")

    # --- SEZIONE INTERVENTO E FIRMA ---
    st.subheader("Gestione Intervento Tecnico")
    
    intervento_esistente = db.get_intervento(ticket_id)
    desc_iniziale = intervento_esistente.get("descrizione", "") if intervento_esistente else ""
    stato_iniziale = intervento_esistente.get("stato", ticket.get("stato", "Aperto"))

    stabili_stati = ["Aperto", "In Lavorazione", "In Attesa", "Risolto", "Chiuso"]
    try:
        idx_stato = stabili_stati.index(stato_iniziale)
    except ValueError:
        idx_stato = 0

    nuovo_stato = st.selectbox("Aggiorna Stato", stabili_stati, index=idx_stato, key=f"stato_{ticket_id}")
    desc_int = st.text_area("Note / Descrizione Intervento", value=desc_iniziale, key=f"desc_{ticket_id}")

    canvas = None
    if nuovo_stato == "Risolto":
        st.write("### Firma del Cliente / Tecnico")
        canvas = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=150,
            width=400,
            drawing_mode="freedraw",
            key=f"canvas_firma_{ticket_id}"
        )

    if st.button("💾 Salva intervento", key=f"btn_salva_int_{ticket_id}"):
        firma_path = None
        
        # Se lo stato è Risolto e c'è il canvas, estraiamo e salviamo la firma
        if nuovo_stato == "Risolto":
            try:
                if canvas is not None and canvas.image_data is not None:
                    img_data = canvas.image_data
                    # Converte l'array in immagine PIL e poi in bytes PNG
                    img = Image.fromarray(img_data.astype("uint8"))
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    
                    # Salva la firma nel database e storage
                    ok, res_path = db.salva_firma_intervento(ticket_id, buf.getvalue(), st.session_state.get("username", "tecnico"))
                    if ok:
                        firma_path = res_path
                    else:
                        st.error(f- "Errore salvataggio firma: {res_path}")
            except Exception as e:
                st.error(f"Errore durante l'elaborazione della firma: {e}")

        # Salvataggio dell'intervento nel database (inclusa la firma_path)
        successo, messaggio = db.salva_intervento_tecnico(
            ticket_id=ticket_id,
            tecnico=st.session_state.get("username", "tecnico"),
            descrizione_intervento=desc_int,
            nuovo_stato=nuovo_stato,
            firma_path=firma_path
        )

        if successo:
            st.success("✅ Intervento salvato con successo!")
            st.rerun()
        else:
            st.error(f"❌ Errore nel salvataggio: {messaggio}")

    # --- DOWNLOAD PDF ---
    st.markdown("---")
    if st.button("📄 Genera e Scarica PDF Report", key=f"pdf_btn_{ticket_id}"):
        try:
            pdf_bytes = pdf_generator.genera_pdf(ticket)
            st.download_button(
                label="📥 Clicca qui per scaricare il PDF",
                data=pdf_bytes,
                file_name=f"report_ticket_{ticket_id}.pdf",
                mime="application/pdf",
                key=f"download_pdf_{ticket_id}"
            )
        except Exception as e:
            st.error(f"Errore nella generazione del PDF: {e}")

        if admin_status:
            st.divider()
            st.markdown("### ⚙️ Azioni Amministratore")
            c1, c2, c3 = st.columns(3)
            
            pdf = pdf_generator.genera_pdf(ticket)
            c1.download_button("📄 Scarica PDF", pdf, file_name=f"ticket_{tid}.pdf", mime="application/pdf", key=f"pdf_{tid}")

            if chiuso:
                if c2.button("🔄 Riapri Ticket", key=f"reopen_{tid}"):
                    db.supabase.table("tickets").update({"stato": "Aperto"}).eq("id", tid).execute()
                    st.session_state["ticket_aperto"] = tid
                    st.rerun()
            elif risolto:
                if c2.button("🔒 Chiudi Ticket", key=f"close_{tid}"):
                    db.supabase.table("tickets").update({"stato": "Chiuso"}).eq("id", tid).execute()
                    st.session_state["ticket_aperto"] = tid
                    st.rerun()
            else:
                c2.info("⏳ In attesa che il tecnico risolva il ticket.")

            if c3.button("🗑️ Elimina", key=f"del_{tid}"):
                db.elimina_ticket_completo(tid)
                if "ticket_aperto" in st.session_state:
                    del st.session_state["ticket_aperto"]
                st.rerun()

def pagina_dashboard():
    st.title("🏠 Dashboard Ticket")
    
    tutti_i_tickets = db.get_tickets()
    if not tutti_i_tickets:
        st.info("Nessun ticket presente nel sistema.")
        return

    if not is_admin():
        utente_attuale = str(st.session_state.get("username", "")).lower()
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

    with st.expander("🔍 Filtri e Ricerca", expanded=False):
        col_search, col_stato, col_prio = st.columns([2, 1, 1])
        testo_ricerca = col_search.text_input("Cerca (Titolo, Descrizione, ID o Creatore)", "").lower()
        stato_selezionato = col_stato.selectbox("Stato", ["Tutti", "Aperto", "In lavorazione", "Risolto", "Chiuso"])
        priorita_selezionata = col_prio.selectbox("Priorità", ["Tutte", "Bassa", "Media", "Alta", "Urgente"])

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

    col1, col2, col3 = st.columns(3)
    col1.metric("Totale Visualizzati", len(tickets_filtrati))
    col2.metric("Aperti / In corso", len([t for t in tickets_filtrati if t.get("stato") in ["Aperto", "In lavorazione"]]))
    col3.metric("Risolti / Chiusi", len([t for t in tickets_filtrati if t.get("stato") in ["Risolto", "Chiuso"]]))

    st.divider()

    if not tickets_filtrati:
        st.warning("Nessun ticket trovato con i criteri di ricerca selezionati.")
        return

    for t in tickets_filtrati:
        mostra_ticket(t)

def pagina_statistiche():
    if not is_admin():
        st.error("Accesso riservato agli amministratori.")
        return

    st.title("📊 Statistiche & Report")
    tickets = db.get_tickets()
    if not tickets:
        st.info("Nessun ticket presente per generare statistiche.")
        return

    df = pd.DataFrame(tickets)
    colonne_utili = {
        'id': 'ID Ticket', 'titolo': 'Titolo', 'categoria': 'Categoria',
        'priorita': 'Priorità', 'stato': 'Stato', 'assegnato_a': 'Tecnico Assegnato',
        'creato_da': 'Creato Da', 'created_at': 'Data Creazione'
    }
    cols = [c for c in colonne_utili.keys() if c in df.columns]
    df_export = df[cols].rename(columns=colonne_utili)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Totale Ticket", len(df))
    kpi2.metric("Ticket Aperti", len(df[df['stato'] == 'Aperto']))
    kpi3.metric("In Lavorazione", len(df[df['stato'] == 'In lavorazione']))
    kpi4.metric("Risolti / Chiusi", len(df[df['stato'].isin(['Risolto', 'Chiuso'])]))

    st.divider()

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("📌 Ticket per Categoria")
        if 'categoria' in df.columns:
            st.bar_chart(df['categoria'].value_counts())
    with col_g2:
        st.subheader("👷 Ticket per Tecnico")
        if 'assegnato_a' in df.columns:
            st.bar_chart(df['assegnato_a'].value_counts())

    st.divider()
    st.subheader("📥 Esporta Report in Excel")
    st.dataframe(df_export, use_container_width=True)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Report Ticket')
    
    st.download_button(
        label="📊 Scarica Report Excel (.xlsx)",
        data=buffer.getvalue(),
        file_name="report_tickets.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

def pagina_amministrazione():
    if not is_admin():
        st.error("Accesso riservato agli amministratori.")
        return

    st.title("👨‍💼 Pannello Amministrazione")
    tab_utenti, tab_cat = st.tabs(["👥 Gestione Utenti", "🏷️ Gestione Categorie"])

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
                            "username": new_user, "password": pass_hash,
                            "ruolo": new_role, "attivo": True
                        }).execute()
                        st.success(f"Utente '{new_user}' creato correttamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore creazione utente: {e}")

        st.divider()
        st.subheader("📋 Lista Utenti")
        res = db.supabase.table("utenti").select("*").order("username").execute()
        for u in (res.data or []):
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
                        "ruolo": nuovo_ruolo, "attivo": (stato_str == "Attivo")
                    }).eq("id", uid).execute()
                    st.success("Utente aggiornato!")
                    st.rerun()

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
