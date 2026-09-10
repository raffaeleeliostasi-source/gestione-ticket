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

    if st.button("⬅️ Torna alla lista ticket"):
        st.session_state.pop("ticket_aperto", None)
        st.rerun()

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
        
        # Se lo stato è Risolto, salviamo la firma dal canvas
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
                st.error(f"Errore durante l'elaborazione della firma: {e}")

        # Salvataggio dell'intervento nel database
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

def mostra_ticket(ticket_id):
    """Funzione alias richiesta dalla dashboard"""
    return mostra_dettaglio_ticket(ticket_id)

def pagina_dashboard():
    st.title("Dashboard Ticket")
    
    # Se un ticket è aperto, mostra i suoi dettagli
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
