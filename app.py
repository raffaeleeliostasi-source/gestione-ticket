import streamlit as st
import views
import database as db


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
    return str(st.session_state.get("ruolo", "")).strip().lower() in {
        "amministratore",
        "admin",
    }


def logout():
    try:
        cookies = views.get_cookie_controller()
        token = cookies.get(views.COOKIE_LOGIN_TOKEN)

        if token:
            db.revoca_login_token(token)

        cookies.remove(views.COOKIE_LOGIN_TOKEN)

    except Exception:
        pass

    for key in ("logged_in", "username", "ruolo"):
        st.session_state[key] = "" if key != "logged_in" else False

    st.session_state.pop("remembered_username", None)
    st.session_state.pop("_cookie_controller_ready", None)

    st.rerun()


# ============================================================
# RIPRISTINO LOGIN PERSISTENTE
# ============================================================

if not st.session_state.logged_in:
    views.ripristina_login_persistente()


if not st.session_state.logged_in:
    views.pagina_login()
    st.stop()


# ============================================================
# SIDEBAR
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
                "📊 Dashboard",
                "🛠️ Gestisci interventi",
                "➕ Nuovo Ticket",
                "📈 Statistiche & Report",
                "⚙️ Amministrazione",
            ],
        )

    else:
        menu = st.radio(
            "Menu",
            [
                "📊 Dashboard",
                "🛠️ Gestisci interventi",
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

if menu == "📊 Dashboard":

    views.pagina_dashboard()


elif menu == "🛠️ Gestisci interventi":

    views.pagina_gestione_interventi()


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
