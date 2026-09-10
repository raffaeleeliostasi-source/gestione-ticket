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
    st.title("🏠 Dashboard")
    tickets = db.get_tickets()
    if not tickets:
        st.info("Nessun ticket presente.")
        return
    st.metric("Totale Ticket", len(tickets))
    for t in tickets[:10]:
        mostra_ticket(t)

def pagina_amministrazione():
    if not is_admin():
        st.error("Accesso riservato.")
        return
    st.title("👨‍💼 Amministrazione")
    st.write("Gestione Utenti e Categorie.")
