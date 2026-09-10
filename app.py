import streamlit as st
import database as db
import views

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="Gestione Ticket",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inizializzazione dello stato di sessione per il login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "ruolo" not in st.session_state:
    st.session_state.ruolo = ""

def main():
    # Gestione schermata di Login se non autenticato
    if not st.session_state.logged_in:
        views.pagina_login()
        return

    # --- SIDEBAR E NAVIGAZIONE ---
    st.sidebar.title(f"👤 {st.session_state.username.capitalize()}")
    st.sidebar.caption(f"Ruolo: **{st.session_state.ruolo}**")
    st.sidebar.divider()

    # Opzioni di menu dinamiche in base al ruolo
    if views.is_admin():
        voci_menu = ["🏠 Dashboard", "➕ Nuovo Ticket", "📊 Statistiche & Report", "👨‍💼 Amministrazione"]
    else:
        voci_menu = ["🏠 Dashboard", "➕ Nuovo Ticket"]

    scelta = st.sidebar.radio("Navigazione", voci_menu)

    st.sidebar.divider()
    
    # Pulsante per il Logout
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.ruolo = ""
        st.rerun()

    # --- ROUTING DELLE PAGINE ---
    if scelta == "🏠 Dashboard":
        views.pagina_dashboard()
    elif scelta == "➕ Nuovo Ticket":
        views.pagina_nuovo_ticket()
    elif scelta == "📊 Statistiche & Report":
        views.pagina_statistiche()
    elif scelta == "👨‍💼 Amministrazione":
        views.pagina_amministrazione()

if __name__ == "__main__":
    main()
