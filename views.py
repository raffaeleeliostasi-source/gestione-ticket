import streamlit as st
from io import BytesIO
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import pandas as pd
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

def mostra_dettaglio_ticket(ticket_id):
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        st.error("Ticket non trovato.")
        return

    if st.button("⬅️ Torna alla lista ticket"):
        st.session_state.pop("ticket_aperto", None)
        st.rerun()

    st.subheader(f"Ticket #{ticket.get('id')} - {ticket.get('titolo', '')}")
    
    st.write(f"**Stato Attuale:** {ticket.get('stato', '')}")
    st.write(f"**Priorità:** {ticket.get('priorita', '')}")
    st.write(f"**Categoria:** {ticket.get('categoria', '')}")
    st.write(f"**Creato da:** {ticket.get('creato_da', '')}")
    st.write(f"**Tecnico Assegnato:** {ticket.get('assegnato_a', 'Nessuno')}")
    
    st.markdown("---")
    st.write(f"**Descrizione:**\n{ticket.get('descrizione', '')}")
    st.markdown("---")

    # --- SEZIONE INTERVENTO E FIRMA ---
    st.subheader("🛠️ Gestione Intervento Tecnico")
    
    intervento_esistente = db.get_intervento(ticket_id)
    desc_iniziale = intervento_esistente.get("descrizione", "") if intervento_esistente else ""
    
    # Stati consentiti per evitare errori di vincolo sul database
    stabili_stati = ["Aperto", "In Lavorazione", "Risolto"]
    stato_attuale_db = intervento_esistente.get("stato", ticket.get("stato", "Aperto"))
    if stato_attuale_db not in stabili_stati:
        stato_attuale_db = "Aperto"

    nuovo_stato = st.selectbox("Aggiorna Stato Intervento", stabili_stati, index=stabili_stati.index(stato_attuale_db), key=f"stato_{ticket_id}")
    desc_int = st.text_area("Note / Descrizione Lavoro", value=desc_iniziale, key=f"desc_{ticket_id}")

    canvas = None
    if nuovo_stato == "Risolto":
        st.write("### ✍️ Firma del Tecnico / Cliente")
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
        
        if nuovo_stato == "Risolto":
            try:
                if canvas is not None and canvas.image_data is not None:
                    img_data = canvas.image_data
                    img = Image.fromarray(img_data.astype("uint8"))
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    
                    ok, res_path = db.salva_firma_intervento(ticket_id, buf.getvalue(), st.session_state.get("username", "tecnico"))
                    if ok:
                        firma_path = res_path
                    else:
                        st.error(f"Errore salvataggio firma: {res_path}")
            except Exception as e:
                st.error(f"Errore elaborazione firma: {e}")

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

    # --- AZIONI AMMINISTRATORE & PDF ---
    st.markdown("---")
    if is_admin():
        st.subheader("⚙️ Pannello Amministratore")
        col_pdf, col_chiudi = st.columns(2)
        
        if col_pdf.button("📄 Genera e Scarica PDF", key=f"pdf_btn_{ticket_id}"):
            try:
                pdf_bytes = pdf_generator.genera_pdf(ticket)
                st.download_button(
                    label="📥 Scarica PDF Report",
                    data=pdf_bytes,
                    file_name=f"report_ticket_{ticket_id}.pdf",
                    mime="application/pdf",
                    key=f"download_pdf_{ticket_id}"
                )
            except Exception as e:
                st.error(f"Errore generazione PDF: {e}")

        if ticket.get("stato") != "Chiuso":
            if col_chiudi.button("🔒 Chiudi Definitivamente", key=f"chiudi_{ticket_id}"):
                db.supabase.table("tickets").update({"stato": "Chiuso"}).eq("id", ticket_id).execute()
                st.success("Ticket chiuso con successo!")
                st.rerun()
        else:
            col_chiudi.info("Ticket già chiuso.")

def mostra_ticket(ticket_id):
    return mostra_dettaglio_ticket(ticket_id)

def pagina_dashboard():
    st.title("🏠 Dashboard Ticket")
    
    if "ticket_aperto" in st.session_state and st.session_state["ticket_aperto"]:
        mostra_ticket(st.session_state["ticket_aperto"])
        return

    tickets = db.get_tickets()
    if not tickets:
        st.info("Nessun ticket presente.")
        return

    st.write("### Elenco Ticket")
    for t in tickets:
        tid = t.get("id")
        titolo = t.get("titolo", "")
        stato = t.get("stato", "")
        col1, col2, col3 = st.columns([1, 4, 2])
        col1.write(f"#{tid}")
        col2.write(f"**{titolo}** ({stato})")
        if col3.button("Apri", key=f"open_{tid}"):
            st.session_state["ticket_aperto"] = tid
            st.rerun()

def pagina_statistiche():
    if not is_admin():
        st.error("Accesso riservato agli amministratori.")
        return
    st.title("📊 Statistiche")
    tickets = db.get_tickets()
    if tickets:
        df = pd.DataFrame(tickets)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nessun dato statistico disponibile.")

def pagina_amministrazione():
    if not is_admin():
        st.error("Accesso riservato agli amministratori.")
        return
    st.title("👨‍💼 Amministrazione")
    st.write("Pannello di controllo utenti e categorie.")
