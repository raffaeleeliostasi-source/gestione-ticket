def pagina_nuovo_ticket():
    st.title("➕ Nuovo Ticket")
    
    # Controlliamo che l'utente sia loggato
    if not st.session_state.get("username"):
        st.error("❌ Errore: Utente non loggato correttamente. Effettua nuovamente il login.")
        return

    categorie = db.get_nomi_categorie_attive()
    tecnici = db.get_tecnici_attivi()

    with st.form("nuovo_ticket_form"):
        titolo = st.text_input("Titolo del problema *")
        descrizione = st.text_area("Descrizione *", height=150)
        
        col1, col2 = st.columns(2)
        categoria = col1.selectbox("Categoria *", categorie) if categorie else None
        priorita = col2.selectbox("Priorità", ["Bassa", "Media", "Alta", "Urgente"])
        assegnato_a = col2.selectbox("👷 Assegna a *", tecnici) if tecnici else None
        
        allegati = st.file_uploader("📁 Allegati (opzionale)", accept_multiple_files=True)
        foto = st.camera_input("📷 Scatta una foto (opzionale)")

        submitted = st.form_submit_button("🎫 Crea Ticket", use_container_width=True)
        
        if submitted:
            if not titolo or not descrizione or not categoria or not assegnato_a:
                st.warning("⚠️ Compila tutti i campi obbligatori contrassegnati.")
                return

            try:
                # 1. Inserimento del ticket principale
                dati_ticket = {
                    "titolo": titolo.strip(),
                    "descrizione": descrizione.strip(),
                    "categoria": categoria,
                    "priorita": priorita,
                    "assegnato_a": assegnato_a,
                    "stato": "Aperto",
                    "creato_da": st.session_state.username
                }
                
                res = db.supabase.table("tickets").insert(dati_ticket).execute()
                
                if res.data and len(res.data) > 0:
                    tid = res.data[0]["id"]
                    
                    # 2. Salvataggio allegati opzionali
                    if allegati:
                        for f in allegati:
                            db.salva_allegato(tid, f)
                            
                    # 3. Salvataggio foto da camera input se presente
                    if foto:
                        db.salva_allegato(tid, foto)
                        
                    st.success(f"✅ Ticket #{tid} creato con successo!")
                    st.balloons()
                else:
                    st.error("❌ Errore sconosciuto durante l'inserimento nel database.")
                    
            except Exception as e:
                st.error(f"❌ Errore critico Supabase: {e}")
