import streamlit as st
import views

st.set_page_config(page_title="Gestione Ticket", page_icon="🎫", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "ruolo" not in st.session_state:
    st.session_state.ruolo = ""
if "pagina" not in st.session_state:
    st.session_state.pagina = "Dashboard"

if not st.session_state.logged_in:
    views.pagina_login()
else:
    with st.sidebar:
        st.title("🎫 Gestione Ticket")
        st.write(f"👤 **{st.session_state.username}** ({st.session_state.ruolo})")
        st.divider()

        if st.button("🏠 Dashboard", use_container_width=True):
            st.session_state.pagina = "Dashboard"
        if st.button("➕ Nuovo Ticket", use_container_width=True):
            st.session_state.pagina = "Nuovo Ticket"
        if views.is_admin() and st.button("👨‍💼 Amministrazione", use_container_width=True):
            st.session_state.pagina = "Amministrazione"
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    if st.session_state.pagina == "Dashboard":
        views.pagina_dashboard()
    elif st.session_state.pagina == "Nuovo Ticket":
        views.pagina_nuovo_ticket()
    elif st.session_state.pagina == "Amministrazione":
        views.pagina_amministrazione()
