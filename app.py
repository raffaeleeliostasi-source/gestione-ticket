import streamlit as st
import views


st.set_page_config(
    page_title="Gestione Ticket",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="auto",
)

# Adattamento globale per smartphone e tablet.
st.markdown(
    """
    <style>
    /* Evita scroll orizzontale accidentale sui display stretti. */
    [data-testid="stAppViewContainer"] {
        overflow-x: hidden;
    }

    @media (max-width: 640px) {
        .block-container {
            padding-left: 0.75rem;
            padding-right: 0.75rem;
            padding-top: 1rem;
        }

        [data-testid="stHorizontalBlock"] {
            gap: 0.6rem;
        }

        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            min-width: 100% !important;
            width: 100% !important;
            flex: 1 1 100% !important;
        }

        [data-testid="stTabs"] [role="tablist"] {
            overflow-x: auto;
            flex-wrap: nowrap;
            scrollbar-width: thin;
        }

        [data-testid="stDataFrame"] {
            max-width: 100%;
            overflow-x: auto;
        }

        img {
            max-width: 100% !important;
            height: auto !important;
        }

        h1 {
            font-size: 1.7rem !important;
        }

        h2 {
            font-size: 1.4rem !important;
        }

        h3 {
            font-size: 1.2rem !important;
        }

        button, [role="button"] {
            min-height: 42px;
        }
    }

    @media (min-width: 641px) and (max-width: 900px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        [data-testid="stHorizontalBlock"] {
            gap: 0.75rem;
        }

        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            min-width: calc(50% - 0.4rem) !important;
            width: calc(50% - 0.4rem) !important;
            flex: 1 1 calc(50% - 0.4rem) !important;
        }

        img {
            max-width: 100% !important;
            height: auto !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
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
    for key in ("logged_in", "username", "ruolo"):
        st.session_state[key] = "" if key != "logged_in" else False
    st.rerun()


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
