import streamlit as st
import time
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
    """Chiude la sessione e invalida il token Ricordami."""
    # Blocca il ripristino automatico durante il rerun provocato dal logout.
    st.session_state["logout_requested"] = True

    # Usiamo prima il token conservato nella sessione: così il logout non
    # dipende dalla lettura asincrona del cookie dal browser.
    token = st.session_state.get("login_persistent_token")
    if not token:
        try:
            token = views.get_cookie_controller().get(views.COOKIE_LOGIN_TOKEN)
            if isinstance(token, dict):
                token = token.get("value")
        except Exception:
            token = None

    if token:
        try:
            db.revoca_login_token(str(token).strip())
        except Exception:
            pass

    # Rimuove il cookie dal browser. Il componente esegue questa operazione
    # lato browser, quindi lasciamo il tempo necessario prima del rerun.
    try:
        views.get_cookie_controller().remove(views.COOKIE_LOGIN_TOKEN)
    except Exception:
        pass

    for key in ("logged_in", "username", "ruolo"):
        st.session_state[key] = "" if key != "logged_in" else False
    st.session_state.pop("remembered_username", None)
    st.session_state.pop("login_persistent_token", None)

    time.sleep(0.5)
    st.rerun()


if not st.session_state.logged_in:
    views.ripristina_login_persistente()

if not st.session_state.logged_in:
    views.pagina_login()
    st.stop()


with st.sidebar:
    st.title("🎫 Gestione Ticket")
    st.write(f"**Utente:** {st.session_state.username}")
    st.write(f"**Ruolo:** {st.session_state.ruolo}")
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
    if st.button("🚪 Logout", use_container_width=True):
        logout()


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
