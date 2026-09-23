import streamlit as st
import views


st.set_page_config(
    page_title="Gestione Ticket",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded",
)


for key, default in {
    "logged_in": False,
    "username": "",
    "ruolo": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def is_admin():
    return str(
        st.session_state.get("ruolo", "")
    ).strip().lower() in {
        "amministratore",
        "admin",
    }


def logout():
    """Chiude la sessione corrente e torna alla schermata di login."""
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["ruolo"] = ""

    st.session_state.pop("login_username", None)
    st.session_state.pop("login_password", None)
    st.session_state.pop("logout_requested", None)

    # Stato relativo ai ticket
    st.session_state.pop("gestisci_ticket_selezionato", None)
    st.session_state.pop("dashboard_ticket_aperto", None)
    st.session_state.pop("gestione_interventi_ticket", None)

    st.rerun()


# ============================================================
# LOGIN
# ============================================================

if not st.session_state.logged_in:
    views.pagina_login()
    st.stop()


# ============================================================
# MENU PRINCIPALE
# ============================================================

with st.sidebar:
    st.title("🎫 Gestione Ticket")

    st.write(
        f"**Utente:** {st.session_state.username}"
    )

    st.write(
        f"**Ruolo:** {st.session_state.ruolo}"
    )

    st.divider()

    if is_admin():
        menu = st.radio(
            "Menu",
            [
                "🎫 Gestisci Ticket",
                "➕ Nuovo Ticket",
                "📈 Statistiche & Report",
                "⚙️ Amministrazione",
            ],
        )
    else:
        menu = st.radio(
            "Menu",
            [
                "🎫 Gestisci Ticket",
                "➕ Nuovo Ticket",
            ],
        )

    st.divider()

    if st.button(
        "🚪 Logout",
        use_container_width=True,
    ):
        logout()


# ============================================================
# PAGINE
# ============================================================

if menu == "🎫 Gestisci Ticket":
    views.pagina_gestisci_ticket()


elif menu == "➕ Nuovo Ticket":
    views.pagina_nuovo_ticket()


elif menu == "📈 Statistiche & Report":
    if is_admin():
        views.pagina_statistiche()
    else:
        st.error("Accesso non autorizzato.")


elif menu == "⚙️ Amministrazione":
    if is_admin():
        views.pagina_amministrazione()
    else:
        st.error("Accesso non autorizzato.")
