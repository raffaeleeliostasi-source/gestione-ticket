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
    """Chiude la sessione e invalida il token Ricordami."""
    # Impedisce che il cookie venga letto e riattivi subito la sessione
    # nel rerun successivo al logout.
    st.session_state["logout_requested"] = True

    token = st.session_state.get("login_persistent_token")

    if token:
        try:
            db.revoca_login_token(str(token).strip())
        except Exception:
            pass

    # Rimuove il cookie. Non leggiamo nuovamente il cookie qui: il componente
    # è asincrono e durante il click potrebbe non avere ancora il valore
    # aggiornato disponibile a Python.
    try:
        views.get_cookie_controller().remove(views.COOKIE_LOGIN_TOKEN)
    except Exception:
        pass

    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["ruolo"] = ""
    st.session_state.pop("remembered_username", None)
    st.session_state.pop("login_persistent_token", None)

    # Il rerun mostra immediatamente il login. Il flag logout_requested
    # impedisce a Ricordami di riaprire la sessione durante questo passaggio.
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
