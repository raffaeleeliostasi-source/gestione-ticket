import base64
from io import BytesIO
from datetime import date

import pandas as pd
import altair as alt
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

import auth
import database as db
import pdf_generator

STATI = ["Aperto", "In Lavorazione", "Risolto", "Chiuso"]
PRIORITA = ["Bassa", "Media", "Alta", "Urgente"]


def is_admin():
    return str(st.session_state.get("ruolo", "")).strip().lower() in {
        "amministratore", "admin"
    }


def _safe(value):
    return "" if value is None else str(value)


def _reset_dashboard_filters():
    st.session_state["dashboard_filter_version"] = (
        int(st.session_state.get("dashboard_filter_version", 0)) + 1
    )


def pagina_login():
    """Schermata di accesso moderna e responsive."""
    from pathlib import Path

    logo_path = Path(__file__).resolve().parent / "assets" / "farfalla.jpg"
    logo_html = ""
    if logo_path.exists():
        import base64
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        logo_html = f'<img class="login-butterfly" src="data:image/jpeg;base64,{logo_b64}" alt="Logo" />'

    st.markdown(
        """
        <style>
        /* ====================================================
           LOGIN — grafica approvata
           ==================================================== */
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 88% 10%, rgba(188, 218, 250, .55) 0, rgba(188, 218, 250, 0) 38%),
                radial-gradient(circle at 8% 90%, rgba(205, 228, 250, .65) 0, rgba(205, 228, 250, 0) 42%),
                #F4F9FE;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stMainBlockContainer"] {
            padding-top: 18px !important;
        }

        .login-page {
            max-width: 760px;
            margin: 0 auto;
        }

        /* Testata superiore */
        .login-brand {
            background: #FFFFFF;
            border-radius: 18px 18px 0 0;
            padding: 24px 34px 18px 34px;
            box-shadow: none;
        }

        .login-brand-row {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 22px;
        }

        .login-butterfly {
            width: 70px;
            height: 88px;
            object-fit: contain;
            mix-blend-mode: multiply;
            flex: 0 0 auto;
        }

        .login-brand-text {
            text-align: left;
        }

        .login-title {
            margin: 0;
            font-family: Arial, Helvetica, sans-serif;
            font-size: 2.85rem;
            line-height: .92;
            font-weight: 800;
            letter-spacing: -1.6px;
            color: #173B68;
        }

        .login-title .ticket {
            display: block;
            color: #B51F2B;
        }

        .login-subtitle {
            margin-top: 13px;
            color: #627B9D;
            font-size: 1rem;
            font-weight: 500;
        }

        .login-divider {
            display: none;
        }

        /* Form separato visivamente dalla testata */
        [data-testid="stForm"] {
            max-width: 760px;
            margin: 0 auto;
            background: rgba(255,255,255,.98);
            border: 0 !important;
            border-radius: 0 0 18px 18px !important;
            padding: 0 28px 27px 28px !important;
            box-shadow: 0 16px 32px rgba(38, 91, 145, .09);
        }

        .login-form-title {
            text-align: center;
            color: #173B68;
            font-size: 1.95rem;
            font-weight: 800;
            margin: 0 0 3px 0;
        }

        .login-form-subtitle {
            text-align: center;
            color: #6C84A5;
            font-size: .93rem;
            margin: 0 0 25px 0;
        }

        [data-testid="stForm"] label {
            color: #173B68 !important;
            font-weight: 600 !important;
            font-size: .82rem !important;
        }

        [data-testid="stForm"] input {
            border: 1px solid #C9DCF2 !important;
            border-radius: 9px !important;
            min-height: 46px !important;
            background: #FFFFFF !important;
        }

        [data-testid="stForm"] input:focus {
            border-color: #2D73E8 !important;
            box-shadow: 0 0 0 2px rgba(45,115,232,.10) !important;
        }

        /* Pulsante rosso come nella schermata approvata */
        [data-testid="stForm"] button[kind="primaryFormSubmit"],
        [data-testid="stForm"] button[type="submit"] {
            width: 220px !important;
            min-height: 46px !important;
            border-radius: 6px !important;
            background: linear-gradient(180deg, #B51F2B, #971520) !important;
            border: none !important;
            color: white !important;
            font-weight: 800 !important;
            font-size: .86rem !important;
            letter-spacing: .04em !important;
            box-shadow: 0 7px 14px rgba(120, 25, 32, .18) !important;
        }

        [data-testid="stForm"] button[type="submit"]:hover {
            background: linear-gradient(180deg, #C32632, #A31622) !important;
        }

        @media (max-width: 640px) {
            .login-page {
                max-width: 100%;
                margin: 0 auto;
            }

            .login-brand {
                border-radius: 16px 16px 0 0;
                padding: 22px 18px 18px 18px;
            }

            .login-brand-row {
                gap: 14px;
            }

            .login-butterfly {
                width: 58px;
                height: 74px;
            }

            .login-title {
                font-size: 2.35rem;
                letter-spacing: -1px;
            }

            .login-subtitle {
                font-size: .82rem;
                margin-top: 8px;
            }

            .login-divider {
                margin-top: 18px;
            }

            [data-testid="stForm"] {
                margin-top: 0 !important;
                border-radius: 0 0 16px 16px !important;
                padding: 0 18px 22px 18px !important;
            }

            .login-form-title {
                font-size: 1.55rem;
            }

            .login-form-subtitle {
                font-size: .86rem;
                margin-bottom: 20px;
            }

            [data-testid="stForm"] button[kind="primaryFormSubmit"],
            [data-testid="stForm"] button[type="submit"] {
                width: 220px !important;
                max-width: 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Colonna centrale: mantiene la schermata compatta su PC e piena su mobile.
    _, login_col, _ = st.columns([1, 2.1, 1])
    with login_col:
        st.markdown(
            f"""
            <div class="login-page">
                <div class="login-brand">
                    <div class="login-brand-row">
                        {logo_html}
                        <div class="login-brand-text">
                            <div class="login-title">
                                Gestione
                                <span class="ticket">Ticket</span>
                            </div>
                            <div class="login-subtitle">Sistema di ticketing e assistenza</div>
                        </div>
                    </div>
                    <div class="login-divider"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form_main"):
            st.markdown(
                '<div class="login-form-title">Accedi alla tua area di lavoro</div>'
                '<div class="login-form-subtitle">Inserisci le tue credenziali per continuare</div>',
                unsafe_allow_html=True,
            )
            # Campi centrati e limitati a 30 caratteri.
            _, login_fields, _ = st.columns([1, 2.2, 1])
            with login_fields:
                username = st.text_input(
                    "Utente",
                    placeholder="Inserisci il tuo utente",
                    max_chars=30,
                    value=st.session_state.get("remembered_username", ""),
                    key="login_username",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Inserisci la tua password",
                    max_chars=30,
                    key="login_password",
                )

                ricordami = st.checkbox(
                    "Ricordami",
                    key="login_ricordami",
                )

            # Pulsante centrato nella pagina.
            _, login_button, _ = st.columns([1, 1, 1])
            with login_button:
                submit = st.form_submit_button(
                    "ACCEDI",
                    use_container_width=True,
                    type="primary",
                )

        if submit:
            username = username.strip().lower()
            if not username or not password:
                st.error("Inserisci utente e password.")
                return

            try:
                user = db.get_utente(username)
            except Exception as e:
                st.error("Errore durante il collegamento al database.")
                st.exception(e)
                return

            if not user or user.get("attivo", True) is False:
                st.error("Credenziali non valide o utente disattivato.")
                return

            if not auth.verifica_password(password, user.get("password", "")):
                st.error("Credenziali non valide.")
                return

            if "$" not in str(user.get("password", "")):
                db.aggiorna_utente(username, password=auth.hash_password(password))

            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.ruolo = user.get("ruolo", "")

            # "Ricordami" mantiene l'username nella sessione Streamlit
            # per i successivi rerun della stessa sessione. Non memorizziamo
            # mai la password. Un vero login persistente oltre la chiusura
            # del browser richiederebbe un sistema di token/cookie dedicato.
            if ricordami:
                st.session_state["remembered_username"] = username
            else:
                st.session_state.pop("remembered_username", None)

            st.rerun()


def pagina_dashboard():
    """Dashboard principale con interfaccia moderna e riepilogo ticket."""
    st.markdown(
        """
        <style>
        .dash-hero {
            background: linear-gradient(135deg, #17365D 0%, #245B91 100%);
            border-radius: 18px;
            padding: 24px 28px;
            color: white;
            margin-bottom: 20px;
            box-shadow: 0 8px 24px rgba(23,54,93,.12);
        }
        .dash-hero h1 {
            margin: 0;
            font-size: 2rem;
            line-height: 1.15;
            color: white;
        }
        .dash-hero p {
            margin: 7px 0 0 0;
            color: rgba(255,255,255,.82);
            font-size: .95rem;
        }
        .dash-user {
            text-align: right;
            font-size: .82rem;
            color: rgba(255,255,255,.82);
            padding-top: 4px;
        }
        .stat-card {
            background: white;
            border: 1px solid #E2E8F0;
            border-radius: 15px;
            padding: 16px 18px;
            min-height: 92px;
            box-shadow: 0 3px 12px rgba(15,23,42,.05);
        }
        .stat-label {
            color: #64748B;
            font-size: .78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .04em;
        }
        .stat-value {
            color: #17365D;
            font-size: 1.65rem;
            font-weight: 800;
            margin-top: 5px;
        }
        .filter-panel {
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 15px;
            padding: 15px 18px 6px 18px;
            margin: 18px 0 14px 0;
        }
        .filter-heading {
            color: #17365D;
            font-size: 1rem;
            font-weight: 800;
            margin-bottom: 8px;
        }
        .result-line {
            color: #64748B;
            font-size: .88rem;
            margin: 10px 0 12px 2px;
        }
        .result-line strong {
            color: #17365D;
        }
        .ticket-card {
            background: white;
            border: 1px solid #E2E8F0;
            border-radius: 15px;
            padding: 17px 19px 14px 19px;
            margin: 0 0 11px 0;
            box-shadow: 0 3px 12px rgba(15,23,42,.045);
        }
        .ticket-id {
            color: #2F75B5;
            font-size: .78rem;
            font-weight: 800;
            letter-spacing: .04em;
            text-transform: uppercase;
        }
        .ticket-title {
            color: #17365D;
            font-size: 1.08rem;
            font-weight: 800;
            margin-top: 2px;
            line-height: 1.25;
        }
        .ticket-desc {
            color: #64748B;
            font-size: .84rem;
            line-height: 1.4;
            margin-top: 8px;
        }
        .meta-label {
            color: #94A3B8;
            font-size: .67rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: .05em;
            margin-bottom: 2px;
        }
        .meta-value {
            color: #334155;
            font-size: .82rem;
            font-weight: 650;
        }
        .badge {
            display: inline-block;
            padding: 4px 9px;
            border-radius: 999px;
            color: white;
            font-size: .70rem;
            font-weight: 800;
            line-height: 1;
        }
        .s-aperto { background: #2563EB; }
        .s-lavorazione { background: #D97706; }
        .s-risolto { background: #15803D; }
        .s-chiuso { background: #64748B; }
        .p-bassa { background: #15803D; }
        .p-media { background: #CA8A04; }
        .p-alta { background: #EA580C; }
        .p-urgente { background: #B91C1C; }
        .empty-card {
            background: #F8FAFC;
            border: 1px dashed #CBD5E1;
            border-radius: 15px;
            padding: 30px;
            text-align: center;
            color: #64748B;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    admin = is_admin()
    username = st.session_state.get("username", "")

    rows = db.get_tickets() if admin else db.get_tickets_tecnico(username)

    user_label = username.replace("_", " ").title() if username else ""
    ruolo_label = st.session_state.get("ruolo", "")

    st.markdown(
        f"""
        <div class="dash-hero">
            <div style="display:flex;justify-content:space-between;gap:20px;align-items:center;">
                <div>
                    <h1>📊 Dashboard</h1>
                    <p>Gestisci e monitora in modo semplice tutte le richieste di assistenza.</p>
                </div>
                <div class="dash-user">
                    <b>{_safe(user_label)}</b><br/>
                    {_safe(ruolo_label)}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not rows:
        st.markdown(
            '<div class="empty-card">🎫<br/><br/><b>Nessun ticket da visualizzare</b><br/>Non sono presenti richieste disponibili per il tuo profilo.</div>',
            unsafe_allow_html=True,
        )
        return

    df = pd.DataFrame(rows)

    def count_status(name):
        if "stato" not in df.columns:
            return 0
        return int((df["stato"].fillna("").astype(str).str.strip() == name).sum())

    total = len(df)
    aperti = count_status("Aperto")
    lavorazione = count_status("In Lavorazione")
    risolti = count_status("Risolto")
    chiusi = count_status("Chiuso")

    stat_cols = st.columns(5)
    stats = [
        ("TOTALE", total),
        ("APERTI", aperti),
        ("IN LAVORAZIONE", lavorazione),
        ("RISOLTI", risolti),
        ("CHIUSI", chiusi),
    ]

    for col, (label, value) in zip(stat_cols, stats):
        with col:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-label">{label}</div>
                    <div class="stat-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="filter-panel">
            <div class="filter-heading">🔎 FILTRA I TICKET</div>
        """,
        unsafe_allow_html=True,
    )

    filter_version = int(st.session_state.get("dashboard_filter_version", 0))

    c1, c2, c3, c4, c5 = st.columns([2.25, 1.2, 1.2, 1.45, .65])

    with c1:
        cerca = st.text_input(
            "Cerca",
            placeholder="Titolo, descrizione o categoria",
            key=f"dashboard_cerca_{filter_version}",
        )

    with c2:
        stato = st.selectbox(
            "Stato",
            ["Tutti"] + STATI,
            key=f"dashboard_stato_{filter_version}",
        )

    with c3:
        priorita = st.selectbox(
            "Priorità",
            ["Tutte"] + PRIORITA,
            key=f"dashboard_priorita_{filter_version}",
        )

    with c4:
        if admin:
            assegnati = sorted(
                [
                    str(x)
                    for x in df.get(
                        "assegnato_a", pd.Series(dtype=str)
                    ).dropna().unique()
                    if str(x).strip()
                ]
            )
            assegnato = st.selectbox(
                "Assegnato a",
                ["Tutti"] + assegnati,
                key=f"dashboard_assegnato_{filter_version}",
                )
        else:
            assegnato = "Tutti"

    with c5:
        st.button(
            "↺",
            key="dashboard_reset",
            help="Azzera tutti i filtri",
            use_container_width=True,
            on_click=_reset_dashboard_filters,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    filtrato = df.copy()

    if cerca:
        mask = (
            filtrato.astype(str)
            .apply(
                lambda col: col.str.contains(
                    cerca, case=False, na=False, regex=False
                )
            )
            .any(axis=1)
        )
        filtrato = filtrato[mask]

    if stato != "Tutti" and "stato" in filtrato.columns:
        filtrato = filtrato[filtrato["stato"] == stato]

    if priorita != "Tutte" and "priorita" in filtrato.columns:
        filtrato = filtrato[filtrato["priorita"] == priorita]

    if admin and assegnato != "Tutti" and "assegnato_a" in filtrato.columns:
        filtrato = filtrato[filtrato["assegnato_a"] == assegnato]

    st.markdown(
        f'<div class="result-line"><strong>{len(filtrato)}</strong> ticket visualizzati</div>',
        unsafe_allow_html=True,
    )

    if filtrato.empty:
        st.markdown(
            '<div class="empty-card">🔍<br/><br/><b>Nessun risultato</b><br/>Prova a modificare i filtri selezionati.</div>',
            unsafe_allow_html=True,
        )
        return

    selected = st.session_state.get("dashboard_ticket_aperto")

    if selected is not None:
        if st.button("← Torna alla Dashboard", key="dashboard_back"):
            st.session_state.pop("dashboard_ticket_aperto", None)
            st.rerun()

        mostra_dettaglio_ticket(int(selected))
        return

    # --------------------------------------------------------
    # SCHEDE TICKET
    # --------------------------------------------------------
    # Il pulsante PDF è volutamente subito dopo il blocco
    # "Assegnato a", come richiesto.
    for _, row in filtrato.iterrows():
        ticket_id = int(row["id"])

        titolo = _safe(row.get("titolo")) or "SENZA TITOLO"
        stato_val = _safe(row.get("stato")) or "—"
        priorita_val = _safe(row.get("priorita")) or "—"
        categoria_val = _safe(row.get("categoria")) or "—"
        tecnico_val = _safe(row.get("assegnato_a")) or "NON ASSEGNATO"

        descrizione = _safe(row.get("descrizione")).strip()
        if len(descrizione) > 150:
            descrizione = descrizione[:147].rstrip() + "..."

        data_ticket = (
            row.get("creato_il")
            or row.get("created_at")
            or row.get("data_creazione")
            or ""
        )
        try:
            data_ticket = db.format_data(data_ticket) if data_ticket else ""
        except Exception:
            data_ticket = _safe(data_ticket)

        stato_class = {
            "Aperto": "s-aperto",
            "In Lavorazione": "s-lavorazione",
            "Risolto": "s-risolto",
            "Chiuso": "s-chiuso",
        }.get(stato_val, "s-chiuso")

        priority_class = {
            "Bassa": "p-bassa",
            "Media": "p-media",
            "Alta": "p-alta",
            "Urgente": "p-urgente",
        }.get(priorita_val, "s-chiuso")

        st.markdown(
            f"""
            <div class="ticket-card">
                <div class="ticket-id">TICKET #{ticket_id}</div>
                <div class="ticket-title">{_safe(titolo)}</div>
                {f'<div class="ticket-desc">{_safe(descrizione)}</div>' if descrizione else ''}
                <div style="height:12px"></div>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;">
                    <div>
                        <div class="meta-label">Stato</div>
                        <span class="badge {stato_class}">{_safe(stato_val)}</span>
                    </div>
                    <div>
                        <div class="meta-label">Priorità</div>
                        <span class="badge {priority_class}">{_safe(priorita_val)}</span>
                    </div>
                    <div>
                        <div class="meta-label">Categoria</div>
                        <div class="meta-value">{_safe(categoria_val)}</div>
                    </div>
                    <div>
                        <div class="meta-label">Assegnato a</div>
                        <div class="meta-value">{_safe(tecnico_val)}</div>
                    </div>
                </div>
                {f'<div style="margin-top:11px;color:#94A3B8;font-size:.72rem;">CREATO IL&nbsp;&nbsp; {_safe(data_ticket)}</div>' if data_ticket else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # L'apertura del ticket è disponibile a tutti.
        # Il download PDF resta riservato all'amministratore.
        if admin:
            col_open, col_pdf = st.columns([5.8, 1.2])
        else:
            col_open = st.container()
            col_pdf = None

        with col_open:
            if st.button(
                "Apri ticket  ›",
                key=f"dashboard_open_{ticket_id}",
                use_container_width=True,
            ):
                st.session_state["dashboard_ticket_aperto"] = ticket_id
                st.rerun()

        if admin and col_pdf is not None:
            with col_pdf:
                try:
                    ticket_completo = db.get_ticket(ticket_id)
                    if not ticket_completo:
                        st.button(
                            "📄",
                            key=f"dashboard_pdf_disabled_{ticket_id}",
                            help="Ticket non disponibile",
                            disabled=True,
                            use_container_width=True,
                        )
                    else:
                        pdf_bytes = pdf_generator.genera_pdf(ticket_completo)
                        st.download_button(
                            "📄",
                            data=pdf_bytes,
                            file_name=f"ticket_{ticket_id}.pdf",
                            mime="application/pdf",
                            key=f"dashboard_pdf_{ticket_id}",
                            help=f"Scarica PDF del ticket #{ticket_id}",
                            use_container_width=True,
                        )
                except Exception as e:
                    st.error(f"PDF #{ticket_id}: {e}")


def pagina_nuovo_ticket():
    st.title("➕ Nuovo Ticket")
    st.markdown("Compila i campi sottostanti per aprire una nuova segnalazione nel sistema.")

    messaggio_ticket = st.session_state.pop("ticket_creato_msg", None)
    if messaggio_ticket:
        st.success(messaggio_ticket)

    categorie = db.get_nomi_categorie_attive()
    tecnici = db.get_tecnici_attivi()

    if not categorie:
        st.warning("Non ci sono categorie attive. Un amministratore deve crearne almeno una.")
        return
    if not tecnici:
        st.warning("Non ci sono tecnici attivi.")
        return

    with st.form("nuovo_ticket_form", clear_on_submit=True):
        st.markdown("### 📝 Dettagli Principali")
        titolo = st.text_input("Titolo del ticket", placeholder="Es. Problema stampante piano terra")
        descrizione = st.text_area(
            "Descrizione dettagliata",
            height=130,
            placeholder="Fornisci quanti più dettagli possibili sul problema..."
        )

        st.markdown("---")
        st.markdown("### ⚙️ Classificazione e Assegnazione")
        c1, c2, c3 = st.columns(3)
        categoria = c1.selectbox("Categoria", categorie)
        priorita = c2.selectbox("Priorità", PRIORITA)
        assegnato_a = c3.selectbox("Assegna a tecnico", tecnici)

        st.markdown("---")
        st.markdown("### 📎 Allegati e Contenuti Multimediali")
        c_file, c_foto = st.columns(2)
        with c_file:
            allegati = st.file_uploader(
                "Documenti o file",
                type=["jpg", "jpeg", "png", "pdf", "doc", "docx", "xls", "xlsx", "txt"],
                accept_multiple_files=True,
            )
        with c_foto:
            foto = st.camera_input("Scatta foto del problema")

        st.markdown("")
        submit = st.form_submit_button("💾 Crea Ticket", use_container_width=True)

    if not submit:
        return

    if not titolo.strip() or not descrizione.strip():
        st.error("Titolo e descrizione sono obbligatori.")
        return

    try:
        ticket = db.crea_ticket(
            titolo=titolo.strip(),
            descrizione=descrizione.strip(),
            categoria=categoria,
            priorita=priorita,
            assegnato_a=assegnato_a,
            creato_da=st.session_state.username,
        )
        ticket_id = ticket["id"]

        for file in allegati or []:
            db.salva_allegato(ticket_id, file)

        if foto is not None:
            db.salva_allegato(ticket_id, foto)

        numero_allegati = len(allegati or []) + (1 if foto is not None else 0)
        if numero_allegati:
            db.registra_evento(
                ticket_id,
                st.session_state.username,
                "Allegati caricati",
                f"Caricati {numero_allegati} allegat{'o' if numero_allegati == 1 else 'i'}.",
            )

        st.session_state["ticket_creato_msg"] = (
            f"✅ Ticket #{ticket_id} creato correttamente!"
        )
        st.rerun()
    except Exception as e:
        st.error("Impossibile creare il ticket.")
        st.exception(e)


def _mostra_allegati(ticket_id):
    allegati = db.get_allegati(ticket_id)
    if not allegati:
        st.info("Nessun allegato.")
        return

    st.subheader("📎 Allegati")
    for allegato in allegati:
        nome = allegato.get("nome_file", "allegato")
        path = allegato.get("percorso_file", "")
        mime = allegato.get("tipo_file", "")

        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"**{nome}**")
            if mime.startswith("image/"):
                try:
                    data = db.scarica_allegato(path)
                    st.image(data, width=500)
                except Exception:
                    st.warning("Impossibile visualizzare l'immagine.")
        with col2:
            try:
                data = db.scarica_allegato(path)
                st.download_button(
                    "⬇️ Scarica",
                    data=data,
                    file_name=nome,
                    mime=mime or "application/octet-stream",
                    key=f"download_{allegato.get('id')}",
                )
            except Exception:
                st.warning("Download non disponibile.")


def _firma_da_canvas(canvas_result):
    """Converte la firma del canvas in PNG, se presente."""
    if canvas_result is None:
        return None

    image_data = getattr(canvas_result, "image_data", None)
    if image_data is None:
        return None
    image = Image.fromarray(image_data.astype("uint8"), "RGBA")
    bbox = image.getbbox()
    if bbox is None:
        return None
    image = image.crop(bbox)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _mostra_cronologia_interventi(ticket_id):
    interventi = db.get_interventi(ticket_id)
    st.markdown("### 📜 Cronologia interventi")
    if not interventi:
        st.info("Nessun intervento registrato.")
        return

    for numero, intervento in enumerate(interventi, start=1):
        iid = intervento.get("id")
        data = db.format_data(intervento.get("data_intervento"))
        tecnico = _safe(intervento.get("tecnico"))
        stato = _safe(intervento.get("stato"))
        descrizione = _safe(intervento.get("descrizione"))
        with st.container(border=True):
            c1, c2, c3 = st.columns([1.2, 2, 1.5])
            c1.write(f"**Intervento #{numero}**")
            c2.write(f"**Tecnico:** {tecnico}")
            c3.write(f"**Data:** {data}")
            st.write(f"**Stato:** {stato}")
            st.write(descrizione)

            foto_path = intervento.get("foto_path")
            if foto_path:
                foto = db.scarica_foto_intervento(foto_path)
                if foto:
                    st.image(foto, caption="Foto intervento", width=500)

            firma_path = intervento.get("firma_path")
            if firma_path:
                firma = db.scarica_firma_intervento(firma_path)
                if firma:
                    st.image(firma, caption="Firma del tecnico", width=300)


def _mostra_storico_ticket(ticket_id):
    """Mostra lo storico audit completo del ticket."""
    eventi = db.get_audit_log(ticket_id)

    st.markdown("### 🧾 Storico attività ticket")

    if not eventi:
        st.info(
            "Nessun evento di audit disponibile. "
            "Gli eventi futuri verranno registrati automaticamente."
        )
        return

    for evento in eventi:
        data = db.format_data(evento.get("data_evento"))
        utente = _safe(evento.get("utente")) or "Sistema"
        azione = _safe(evento.get("azione")) or "Evento"
        dettagli = _safe(evento.get("dettagli"))

        with st.container(border=True):
            st.markdown(f"**{azione}**")
            st.caption(f"👤 {utente}  •  📅 {data}")
            if dettagli:
                st.write(dettagli)


def mostra_dettaglio_ticket(ticket_id):
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        st.error("Ticket non trovato.")
        return

    admin = is_admin()
    username = st.session_state.username
    assegnato = _safe(ticket.get("assegnato_a"))
    stato_attuale = _safe(ticket.get("stato"))

    if not admin and assegnato != username:
        st.error("Accesso non autorizzato a questo ticket.")
        return

    # Carica sempre tutta la cronologia: ogni intervento è una riga distinta.
    interventi = db.get_interventi(ticket_id)
    ultimo_intervento = interventi[-1] if interventi else None

    # --------------------------------------------------------
    # INTESTAZIONE E DATI DEL TICKET
    # --------------------------------------------------------
    st.markdown(
        """
        <style>
        .detail-head {
            background: linear-gradient(135deg, #17365D 0%, #245B91 100%);
            border-radius: 16px;
            padding: 20px 24px;
            color: white;
            margin: 12px 0 16px 0;
            box-shadow: 0 6px 18px rgba(15,23,42,.10);
        }
        .detail-id {
            font-size: .76rem;
            font-weight: 800;
            letter-spacing: .06em;
            text-transform: uppercase;
            opacity: .82;
        }
        .detail-title {
            font-size: 1.55rem;
            font-weight: 800;
            line-height: 1.2;
            margin-top: 4px;
        }
        .detail-info {
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 14px 16px 4px 16px;
            margin-bottom: 16px;
        }
        .detail-section-title {
            color: #17365D;
            font-size: 1.05rem;
            font-weight: 800;
            margin: 18px 0 9px 0;
        }
        .detail-description {
            background: white;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 14px 16px;
            color: #334155;
            line-height: 1.55;
            margin-bottom: 16px;
        }
        .intervention-head {
            color: #17365D;
            font-weight: 800;
            font-size: .98rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="detail-head">
            <div class="detail-id">🎫 TICKET #{ticket_id}</div>
            <div class="detail-title">{_safe(ticket.get('titolo'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="detail-info">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"**STATO**<br>{_safe(ticket.get('stato'))}", unsafe_allow_html=True)
    c2.markdown(f"**PRIORITÀ**<br>{_safe(ticket.get('priorita'))}", unsafe_allow_html=True)
    c3.markdown(f"**CATEGORIA**<br>{_safe(ticket.get('categoria'))}", unsafe_allow_html=True)
    c4.markdown(f"**TECNICO**<br>{assegnato or 'NON ASSEGNATO'}", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="detail-section-title">👤 Informazioni</div>', unsafe_allow_html=True)
    st.write(f"**Creato da:** {_safe(ticket.get('creato_da'))}")

    st.markdown('<div class="detail-section-title">📝 Descrizione</div>', unsafe_allow_html=True)
    descrizione_ticket = _safe(ticket.get("descrizione"))
    st.markdown(
        f'<div class="detail-description">{descrizione_ticket.replace(chr(10), "<br>")}</div>',
        unsafe_allow_html=True,
    )

    _mostra_allegati(ticket_id)

    # --------------------------------------------------------
    # CRONOLOGIA INTERVENTI
    # --------------------------------------------------------
    if interventi:
        st.markdown("### 🕘 Cronologia interventi")

        for numero, intervento in enumerate(interventi, start=1):
            stato_int = _safe(intervento.get("stato")) or "—"
            tecnico_int = _safe(intervento.get("tecnico")) or "—"
            data_int = db.format_data(intervento.get("data_intervento"))
            descrizione_int = _safe(intervento.get("descrizione"))

            with st.container(border=True):
                st.markdown(
                    f'<div class="intervention-head">🔧 Intervento #{numero} — {_safe(stato_int)}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(f"👷 {tecnico_int}  •  📅 {data_int}")
                st.write(descrizione_int)

                foto_path = intervento.get("foto_path")
                if foto_path:
                    try:
                        foto_bytes = db.scarica_foto_intervento(foto_path)
                        if foto_bytes:
                            st.image(
                                foto_bytes,
                                caption=f"📷 Foto intervento #{numero}",
                                width=500,
                            )
                    except Exception:
                        st.warning("Foto dell'intervento presente ma non visualizzabile.")

                firma_path = intervento.get("firma_path")
                firma_bytes = None
                if firma_path:
                    try:
                        firma_bytes = db.scarica_firma_intervento(firma_path)
                    except Exception:
                        firma_bytes = None

                # Fallback sul percorso standard, utile per eventuali record
                # precedenti in cui firma_path non era valorizzato correttamente.
                if not firma_bytes and intervento.get("id"):
                    fallback_path = (
                        f"firme/{ticket_id}/intervento_{intervento.get('id')}/firma.png"
                    )
                    try:
                        firma_bytes = db.scarica_firma_intervento(fallback_path)
                        if firma_bytes:
                            db.supabase.table("ticket_interventi").update(
                                {"firma_path": fallback_path}
                            ).eq("id", intervento.get("id")).execute()
                    except Exception:
                        firma_bytes = None

                if firma_bytes:
                    st.image(
                        firma_bytes,
                        caption=f"✍️ Firma intervento #{numero}",
                        width=350,
                    )
    else:
        st.info("Nessun intervento tecnico registrato.")

    # --------------------------------------------------------
    # STORICO COMPLETO DEL TICKET
    # --------------------------------------------------------
    _mostra_storico_ticket(ticket_id)

    # --------------------------------------------------------
    # AMMINISTRATORE
    # --------------------------------------------------------
    if admin:
        with st.container(border=True):
            st.markdown("### 🛠️ Gestione Amministrativa")
            st.write(f"**Tecnico assegnato:** {assegnato or '—'}")
            st.write(f"**Stato attuale:** {stato_attuale or '—'}")

            if ultimo_intervento:
                st.write("**Ultimo intervento:**")
                st.write(_safe(ultimo_intervento.get("descrizione")))

            col_pdf, col_close = st.columns(2)

            with col_pdf:
                try:
                    pdf_bytes = pdf_generator.genera_pdf(ticket)
                    st.download_button(
                        "📄 Scarica PDF",
                        data=pdf_bytes,
                        file_name=f"ticket_{ticket_id}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{ticket_id}",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error("Errore nella generazione PDF.")
                    st.exception(e)

            with col_close:
                if stato_attuale != "Chiuso":
                    if st.button(
                        "🔒 Chiudi ticket",
                        key=f"close_{ticket_id}",
                        use_container_width=True,
                    ):
                        try:
                            if db.chiudi_ticket(ticket_id, username):
                                st.success("Ticket chiuso.")
                                st.rerun()
                        except Exception as e:
                            st.error("Errore nella chiusura del ticket.")
                            st.exception(e)

        return

    # --------------------------------------------------------
    # TECNICO — NUOVO INTERVENTO
    # --------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 🔧 Nuovo intervento tecnico")

        if stato_attuale in {"Risolto", "Chiuso"}:
            st.success(
                f"Ticket {stato_attuale.lower()}: non sono consentiti nuovi interventi."
            )
            return

        st.caption(
            "Ogni salvataggio crea un nuovo intervento e conserva tutto lo storico precedente."
        )

        stato_options = ["Aperto", "In Lavorazione", "Risolto"]
        stato = st.selectbox(
            "Stato dell'intervento",
            stato_options,
            index=(
                stato_options.index(stato_attuale)
                if stato_attuale in stato_options
                else 0
            ),
            key=f"tech_state_{ticket_id}",
        )

        note = st.text_area(
            "Descrizione dell'intervento",
            placeholder="Descrivi dettagliatamente il lavoro eseguito...",
            key=f"tech_note_{ticket_id}",
            height=140,
        )

        c_foto, c_camera = st.columns(2)
        with c_foto:
            foto_file = st.file_uploader(
                "📷 Carica foto intervento",
                type=["jpg", "jpeg", "png"],
                key=f"tech_photo_{ticket_id}",
            )
        with c_camera:
            foto_camera = st.camera_input(
                "📸 Scatta foto intervento",
                key=f"tech_camera_{ticket_id}",
            )

        canvas_result = None
        if stato == "Risolto":
            st.markdown("#### ✍️ Firma del tecnico")
            st.info(
                "Per risolvere il ticket è obbligatoria la firma grafica del tecnico."
            )
            canvas_result = st_canvas(
                fill_color="rgba(255,255,255,0)",
                stroke_width=2,
                stroke_color="#000000",
                background_color="#FFFFFF",
                height=180,
                width=600,
                drawing_mode="freedraw",
                key=f"firma_intervento_{ticket_id}",
                return_image_data=True,
            )

        st.markdown("")
        if st.button(
            "💾 Salva nuovo intervento",
            key=f"tech_save_{ticket_id}",
            use_container_width=True,
        ):
            try:
                if not note.strip():
                    st.error("La descrizione dell'intervento è obbligatoria.")
                    return

                firma_bytes = None
                if stato == "Risolto":
                    firma_bytes = _firma_da_canvas(canvas_result)
                    if not firma_bytes:
                        st.error("Inserisci la firma prima di risolvere il ticket.")
                        return

                # 1. Crea SEMPRE una nuova riga e recupera il suo ID.
                # Uso parametri posizionali per mantenere compatibilita
                # anche con la versione precedente di database.py.
                intervento = db.salva_intervento_tecnico(
                    ticket_id,
                    username,
                    note,
                    stato,
                )

                if not intervento:
                    st.error("L'intervento non è stato creato.")
                    return

                intervento_id = intervento.get("id")
                if not intervento_id:
                    st.error("Supabase non ha restituito l'ID del nuovo intervento.")
                    return

                # 2. La foto viene associata ESATTAMENTE a questa riga.
                foto_da_salvare = foto_file or foto_camera
                if foto_da_salvare is not None:
                    percorso_foto = db.salva_foto_intervento(
                        intervento_id=intervento_id,
                        ticket_id=ticket_id,
                        file=foto_da_salvare,
                    )
                    if not percorso_foto:
                        st.warning(
                            "L'intervento è stato salvato, ma la foto non è stata associata correttamente."
                        )

                # 3. La firma viene associata ESATTAMENTE a questa riga.
                if firma_bytes is not None:
                    percorso_firma = db.salva_firma_intervento(
                        intervento_id=intervento_id,
                        ticket_id=ticket_id,
                        file_bytes=firma_bytes,
                        filename="firma.png",
                    )
                    if not percorso_firma:
                        raise RuntimeError("La firma non è stata associata correttamente.")

                    # La firma è stata salvata e associata all'intervento.
                    # Non eseguiamo un download immediato da Storage: alcune
                    # configurazioni/policy di Storage possono impedire la
                    # rilettura immediata pur avendo completato correttamente
                    # l'upload. L'eventuale errore reale viene già intercettato
                    # da salva_firma_intervento().

                st.session_state["intervento_successo"] = {
                    "ticket_id": ticket_id,
                    "messaggio": (
                        f"✅ Intervento #{intervento_id} salvato correttamente. "
                        f"Ticket aggiornato a: {stato}."
                    ),
                }
                st.rerun()

            except PermissionError as e:
                st.error(str(e))
            except Exception as e:
                st.error("Errore nel salvataggio dell'intervento.")
                st.exception(e)



def pagina_gestione_interventi():
    """Area operativa dedicata al lavoro del tecnico."""
    admin = is_admin()
    username = st.session_state.get("username", "")

    tickets = db.get_tickets() if admin else db.get_tickets_tecnico(username)

    if not tickets:
        st.title("🛠️ Gestisci gli interventi")
        st.info("Non ci sono ticket disponibili per la gestione degli interventi.")
        return

    df = pd.DataFrame(tickets)

    # ========================================================
    # DETTAGLIO TICKET
    # ========================================================
    selected = st.session_state.get("gestione_interventi_ticket")

    if selected is not None:
        if st.button(
            "← Torna alla mia area di lavoro",
            key="gestione_interventi_back",
        ):
            st.session_state.pop("gestione_interventi_ticket", None)
            st.rerun()

        mostra_dettaglio_ticket(int(selected))
        return

    # ========================================================
    # AMMINISTRATORE
    # ========================================================
    # Per l'amministratore manteniamo la gestione generale degli
    # interventi, mentre la nuova area operativa è dedicata al tecnico.
    if admin:
        st.title("🛠️ Gestisci gli interventi")
        st.caption(
            "Consulta lo storico degli interventi e gestisci i ticket."
        )

        stati = (
            df["stato"].fillna("")
            if "stato" in df.columns
            else pd.Series(dtype=str)
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ticket", len(df))
        c2.metric("Aperti", int((stati == "Aperto").sum()))
        c3.metric("In lavorazione", int((stati == "In Lavorazione").sum()))
        c4.metric("Risolti", int((stati == "Risolto").sum()))

        with st.container(border=True):
            st.markdown("### 🔎 Filtra ticket")
            f1, f2, f3 = st.columns([2, 1.2, 1.2])

            with f1:
                ricerca = st.text_input(
                    "Cerca",
                    placeholder="Numero, titolo, descrizione...",
                    key="gestione_interventi_cerca",
                ).strip()

            with f2:
                filtro_stato = st.selectbox(
                    "Stato",
                    ["Tutti", "Aperto", "In Lavorazione", "Risolto", "Chiuso"],
                    key="gestione_interventi_stato",
                )

            with f3:
                presenti = []
                if "priorita" in df.columns:
                    presenti = [
                        str(x)
                        for x in df["priorita"].dropna().unique()
                        if str(x)
                    ]
                priorita_disponibili = ["Tutte"] + [
                    x for x in PRIORITA if x in presenti
                ]
                for x in presenti:
                    if x not in priorita_disponibili:
                        priorita_disponibili.append(x)

                filtro_priorita = st.selectbox(
                    "Priorità",
                    priorita_disponibili,
                    key="gestione_interventi_priorita",
                )

        filtrato = df.copy()

        if ricerca:
            mask = filtrato.astype(str).apply(
                lambda col: col.str.contains(
                    ricerca,
                    case=False,
                    na=False,
                    regex=False,
                )
            ).any(axis=1)
            filtrato = filtrato[mask]

        if filtro_stato != "Tutti" and "stato" in filtrato.columns:
            filtrato = filtrato[filtrato["stato"] == filtro_stato]

        if filtro_priorita != "Tutte" and "priorita" in filtrato.columns:
            filtrato = filtrato[filtrato["priorita"] == filtro_priorita]

        st.caption(f"{len(filtrato)} ticket visualizzati")

        if filtrato.empty:
            st.info("Nessun ticket corrisponde ai filtri selezionati.")
            return

        for _, row in filtrato.iterrows():
            ticket_id = int(row["id"])
            titolo = _safe(row.get("titolo")) or "Senza titolo"
            stato = _safe(row.get("stato")) or "—"
            priorita = _safe(row.get("priorita")) or "—"
            categoria = _safe(row.get("categoria")) or "—"
            tecnico = _safe(row.get("assegnato_a")) or "Non assegnato"

            interventi = db.get_interventi(ticket_id)
            ultimo = interventi[-1] if interventi else None

            with st.container(border=True):
                c1, c2 = st.columns([4, 1.2])
                with c1:
                    st.markdown(f"### 🎫 #{ticket_id} — {titolo}")
                    st.write(
                        f"**Stato:** {stato}  •  **Priorità:** {priorita}  •  "
                        f"**Categoria:** {categoria}"
                    )
                    st.caption(
                        f"👷 Tecnico: {tecnico}  •  "
                        f"🛠️ Interventi registrati: {len(interventi)}"
                    )
                    if ultimo:
                        st.write(
                            f"**Ultimo intervento:** "
                            f"{_safe(ultimo.get('descrizione'))}"
                        )
                        st.caption(
                            f"{_safe(ultimo.get('tecnico'))} • "
                            f"{db.format_data(ultimo.get('data_intervento'))} • "
                            f"{_safe(ultimo.get('stato'))}"
                        )
                with c2:
                    if st.button(
                        "🛠️ Gestisci",
                        key=f"gestisci_interventi_{ticket_id}",
                        use_container_width=True,
                    ):
                        st.session_state["gestione_interventi_ticket"] = ticket_id
                        st.rerun()

        return

    # ========================================================
    # TECNICO — VERA AREA DI LAVORO
    # ========================================================
    user_label = username.replace("_", " ").title() if username else "Tecnico"

    stati = (
        df["stato"].fillna("").astype(str).str.strip()
        if "stato" in df.columns
        else pd.Series(dtype=str)
    )

    aperti = df[stati == "Aperto"].copy()
    lavorazione = df[stati == "In Lavorazione"].copy()
    risolti = df[stati == "Risolto"].copy()
    chiusi = df[stati == "Chiuso"].copy()

    # Priorità operative: Urgente → Alta → Media → Bassa.
    ordine_priorita = {
        "Urgente": 0,
        "Alta": 1,
        "Media": 2,
        "Bassa": 3,
    }

    def ordina_operativi(frame):
        frame = frame.copy()
        if frame.empty:
            return frame

        if "priorita" in frame.columns:
            frame["_ordine_priorita"] = (
                frame["priorita"]
                .fillna("")
                .map(ordine_priorita)
                .fillna(99)
            )
        else:
            frame["_ordine_priorita"] = 99

        if "id" in frame.columns:
            frame = frame.sort_values(
                by=["_ordine_priorita", "id"],
                ascending=[True, False],
                kind="stable",
            )
        else:
            frame = frame.sort_values(
                by=["_ordine_priorita"],
                ascending=[True],
                kind="stable",
            )

        return frame.drop(columns=["_ordine_priorita"])

    aperti = ordina_operativi(aperti)
    lavorazione = ordina_operativi(lavorazione)
    risolti = ordina_operativi(risolti)
    chiusi = ordina_operativi(chiusi)

    # --------------------------------------------------------
    # INTESTAZIONE
    # --------------------------------------------------------
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #17365D, #245B8F);
            border-radius: 18px;
            padding: 24px 28px;
            margin-bottom: 18px;
            color: white;
        ">
            <div style="font-size: 2rem; font-weight: 800;">
                🛠️ La mia area di lavoro
            </div>
            <div style="font-size: 1rem; opacity: .92; margin-top: 6px;">
                Ciao <b>{_safe(user_label)}</b> — qui trovi i ticket assegnati
                e le attività che richiedono il tuo intervento.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # RIEPILOGO OPERATIVO
    # --------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎫 Totali", len(df))
    c2.metric("🟡 Da lavorare", len(aperti))
    c3.metric("🟠 In lavorazione", len(lavorazione))
    c4.metric("🟢 Risolti", len(risolti))

    st.markdown("")

    # --------------------------------------------------------
    # FILTRI
    # --------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 🔎 Cerca nella mia area")

        f1, f2 = st.columns([2.5, 1])

        with f1:
            ricerca = st.text_input(
                "Cerca ticket",
                placeholder="Numero, titolo, descrizione, categoria...",
                key="gestione_interventi_cerca",
            ).strip()

        with f2:
            priorita_filtro = st.selectbox(
                "Priorità",
                ["Tutte"] + list(PRIORITA),
                key="gestione_interventi_priorita",
            )

    def applica_filtri(frame):
        if frame.empty:
            return frame

        risultato = frame.copy()

        if ricerca:
            mask = risultato.astype(str).apply(
                lambda col: col.str.contains(
                    ricerca,
                    case=False,
                    na=False,
                    regex=False,
                )
            ).any(axis=1)
            risultato = risultato[mask]

        if (
            priorita_filtro != "Tutte"
            and "priorita" in risultato.columns
        ):
            risultato = risultato[
                risultato["priorita"] == priorita_filtro
            ]

        return risultato

    aperti = applica_filtri(aperti)
    lavorazione = applica_filtri(lavorazione)
    risolti = applica_filtri(risolti)
    chiusi = applica_filtri(chiusi)

    # --------------------------------------------------------
    # CARD TICKET
    # --------------------------------------------------------
    def mostra_card_ticket(row, tipo):
        ticket_id = int(row["id"])
        titolo = _safe(row.get("titolo")) or "Senza titolo"
        stato = _safe(row.get("stato")) or "—"
        priorita = _safe(row.get("priorita")) or "—"
        categoria = _safe(row.get("categoria")) or "—"

        interventi = db.get_interventi(ticket_id)
        ultimo = interventi[-1] if interventi else None

        icone_stato = {
            "Aperto": "🟡",
            "In Lavorazione": "🟠",
            "Risolto": "🟢",
            "Chiuso": "⚪",
        }
        icona = icone_stato.get(stato, "🎫")

        st.markdown(
            f"""
            <div style="
                border: 1px solid #E2E8F0;
                border-radius: 14px;
                padding: 16px 18px 12px 18px;
                margin-bottom: 8px;
                background: #FFFFFF;
            ">
                <div style="font-size: 1.12rem; font-weight: 800; color: #17365D;">
                    {icona} #{ticket_id} — {_safe(titolo)}
                </div>
                <div style="margin-top: 7px; color: #475569; font-size: .88rem;">
                    <b>Stato:</b> {_safe(stato)}
                    &nbsp; • &nbsp;
                    <b>Priorità:</b> {_safe(priorita)}
                    &nbsp; • &nbsp;
                    <b>Categoria:</b> {_safe(categoria)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns([4, 1])

        with c1:
            if ultimo:
                st.caption(
                    f"🛠️ Ultimo intervento: "
                    f"{_safe(ultimo.get('descrizione'))}"
                )
                st.caption(
                    f"{_safe(ultimo.get('tecnico'))} • "
                    f"{db.format_data(ultimo.get('data_intervento'))} • "
                    f"{_safe(ultimo.get('stato'))} • "
                    f"Interventi totali: {len(interventi)}"
                )
            else:
                st.caption(
                    "🆕 Nessun intervento ancora registrato."
                )

        with c2:
            if st.button(
                "🛠️ Apri ticket",
                key=f"area_tecnico_ticket_{tipo}_{ticket_id}",
                use_container_width=True,
            ):
                st.session_state["gestione_interventi_ticket"] = ticket_id
                st.rerun()

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # --------------------------------------------------------
    # SEZIONE OPERATIVA
    # --------------------------------------------------------
    def mostra_sezione(frame, titolo, descrizione, emoji, empty_text):
        st.markdown(f"### {emoji} {titolo}")
        st.caption(descrizione)

        if frame.empty:
            st.info(empty_text)
            return

        st.caption(f"{len(frame)} ticket")
        for _, row in frame.iterrows():
            mostra_card_ticket(row, titolo)

    mostra_sezione(
        lavorazione,
        "In lavorazione",
        "Ticket sui quali stai già intervenendo.",
        "🟠",
        "Nessun ticket attualmente in lavorazione.",
    )

    st.divider()

    mostra_sezione(
        aperti,
        "Da prendere in carico",
        "Ticket assegnati a te che non sono ancora in lavorazione.",
        "🟡",
        "Non hai ticket aperti da prendere in carico.",
    )

    st.divider()

    mostra_sezione(
        risolti,
        "Risolti — in attesa di chiusura",
        "Hai completato l'intervento. Il ticket resta disponibile fino alla chiusura amministrativa.",
        "🟢",
        "Non ci sono ticket risolti in attesa di chiusura.",
    )

    # --------------------------------------------------------
    # STORICO CHIUSI
    # --------------------------------------------------------
    st.divider()

    with st.expander(
        f"📁 Storico ticket chiusi ({len(chiusi)})",
        expanded=False,
    ):
        st.caption(
            "I ticket chiusi sono consultabili come storico e non "
            "compaiono più nella parte operativa principale."
        )

        if chiusi.empty:
            st.info("Nessun ticket chiuso nello storico.")
        else:
            for _, row in chiusi.iterrows():
                mostra_card_ticket(row, "chiuso")

def pagina_statistiche():
    if not is_admin():
        st.error("Accesso non autorizzato.")
        return

    st.title("📈 Statistiche & Report")
    st.caption("Cruscotto amministrativo per monitorare andamento, carichi di lavoro e stato dei ticket.")

    rows = db.get_tickets()
    df = pd.DataFrame(rows)

    if df.empty:
        st.info("Non ci sono ticket disponibili per generare le statistiche.")
        return

    # Normalizzazione minima dei campi utilizzati dal report.
    for col in ["stato", "priorita", "categoria", "assegnato_a"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()

    # --------------------------------------------------------
    # FILTRI REPORT
    # --------------------------------------------------------
    st.markdown("### 🔎 Filtra il report")
    with st.container(border=True):
        f1, f2, f3, f4 = st.columns(4)

        with f1:
            stati_presenti = [x for x in STATI if x in set(df["stato"])]
            filtro_stato = st.selectbox(
                "Stato",
                ["Tutti"] + stati_presenti,
                key="statistiche_stato",
            )

        with f2:
            priorita_presenti = [x for x in PRIORITA if x in set(df["priorita"])]
            filtro_priorita = st.selectbox(
                "Priorità",
                ["Tutte"] + priorita_presenti,
                key="statistiche_priorita",
            )

        with f3:
            categorie = sorted([x for x in df["categoria"].unique() if x])
            filtro_categoria = st.selectbox(
                "Categoria",
                ["Tutte"] + categorie,
                key="statistiche_categoria",
            )

        with f4:
            tecnici = sorted([x for x in df["assegnato_a"].unique() if x])
            filtro_tecnico = st.selectbox(
                "Tecnico",
                ["Tutti"] + tecnici,
                key="statistiche_tecnico",
            )

    filtrato = df.copy()
    if filtro_stato != "Tutti":
        filtrato = filtrato[filtrato["stato"] == filtro_stato]
    if filtro_priorita != "Tutte":
        filtrato = filtrato[filtrato["priorita"] == filtro_priorita]
    if filtro_categoria != "Tutte":
        filtrato = filtrato[filtrato["categoria"] == filtro_categoria]
    if filtro_tecnico != "Tutti":
        filtrato = filtrato[filtrato["assegnato_a"] == filtro_tecnico]

    if filtrato.empty:
        st.warning("Nessun ticket corrisponde ai filtri selezionati.")
        return

    st.caption(f"Report filtrato: **{len(filtrato)} ticket** su {len(df)} totali.")

    # --------------------------------------------------------
    # KPI
    # --------------------------------------------------------
    stati_filtrati = filtrato["stato"]
    total = len(filtrato)
    aperti = int((stati_filtrati == "Aperto").sum())
    lavorazione = int((stati_filtrati == "In Lavorazione").sum())
    risolti = int((stati_filtrati == "Risolto").sum())
    chiusi = int((stati_filtrati == "Chiuso").sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🎫 Totali", total)
    c2.metric("🟡 Aperti", aperti)
    c3.metric("🟠 In lavorazione", lavorazione)
    c4.metric("🟢 Risolti", risolti)
    c5.metric("⚪ Chiusi", chiusi)

    st.markdown("")

    # --------------------------------------------------------
    # GRAFICI PRINCIPALI
    # --------------------------------------------------------
    # I grafici sono realizzati con Altair in modalità NON interattiva:
    # la rotella del mouse non effettua zoom e non modifica la scala.
    # L'asse Y è esplicitamente quantitativo con origine a zero.
    def _grafico_barre(data, categoria, valore, ordinamento=None, altezza=280):
        chart = (
            alt.Chart(data)
            .mark_bar()
            .encode(
                x=alt.X(
                    f"{categoria}:N",
                    sort=ordinamento,
                    axis=alt.Axis(labelAngle=-90),
                ),
                y=alt.Y(
                    f"{valore}:Q",
                    scale=alt.Scale(zero=True),
                    axis=alt.Axis(title=None),
                ),
                tooltip=[
                    alt.Tooltip(f"{categoria}:N", title=categoria.capitalize()),
                    alt.Tooltip(f"{valore}:Q", title="Ticket", format="d"),
                ],
            )
            .properties(height=altezza)
        )
        return chart

    g1, g2 = st.columns(2)

    with g1:
        st.markdown("### 📊 Ticket per stato")
        stato_counts = (
            filtrato["stato"]
            .value_counts()
            .reindex([x for x in STATI if x in set(filtrato["stato"])], fill_value=0)
            .reset_index()
        )
        stato_counts.columns = ["stato", "ticket"]
        st.altair_chart(
            _grafico_barre(stato_counts, "stato", "ticket", STATI),
            use_container_width=True,
            theme=None,
        )

    with g2:
        st.markdown("### 🚦 Ticket per priorità")
        priorita_counts = (
            filtrato["priorita"]
            .value_counts()
            .reindex([x for x in PRIORITA if x in set(filtrato["priorita"])], fill_value=0)
            .reset_index()
        )
        priorita_counts.columns = ["priorita", "ticket"]
        st.altair_chart(
            _grafico_barre(priorita_counts, "priorita", "ticket", PRIORITA),
            use_container_width=True,
            theme=None,
        )

    g3, g4 = st.columns(2)

    with g3:
        st.markdown("### 🗂️ Ticket per categoria")
        categoria_counts = (
            filtrato["categoria"]
            .replace("", "Non specificata")
            .value_counts()
            .rename_axis("categoria")
            .reset_index(name="ticket")
        )
        st.altair_chart(
            _grafico_barre(categoria_counts, "categoria", "ticket",
                           categoria_counts["categoria"].tolist()),
            use_container_width=True,
            theme=None,
        )

    with g4:
        st.markdown("### 👷 Ticket per tecnico")
        tecnico_counts = (
            filtrato["assegnato_a"]
            .replace("", "Non assegnato")
            .value_counts()
            .rename_axis("tecnico")
            .reset_index(name="ticket")
        )
        st.altair_chart(
            _grafico_barre(tecnico_counts, "tecnico", "ticket",
                           tecnico_counts["tecnico"].tolist()),
            use_container_width=True,
            theme=None,
        )

    # --------------------------------------------------------
    # TABELLA REPORT
    # --------------------------------------------------------
    st.markdown("### 📋 Dettaglio ticket")

    report_df = filtrato.copy()
    for col in ["data_chiusura", "chiuso_da"]:
        if col not in report_df.columns:
            report_df[col] = ""

    preferred = [
        "id", "titolo", "categoria", "priorita", "stato",
        "assegnato_a", "creato_da", "data_chiusura", "chiuso_da", "descrizione"
    ]
    visible = [c for c in preferred if c in report_df.columns]
    report_view = report_df[visible].copy()

    st.dataframe(
        report_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "titolo": st.column_config.TextColumn("Titolo"),
            "descrizione": st.column_config.TextColumn("Descrizione", width="large"),
            "categoria": st.column_config.TextColumn("Categoria"),
            "priorita": st.column_config.TextColumn("Priorità"),
            "stato": st.column_config.TextColumn("Stato"),
            "assegnato_a": st.column_config.TextColumn("Tecnico"),
            "creato_da": st.column_config.TextColumn("Creato da"),
            "data_chiusura": st.column_config.TextColumn("Data chiusura"),
            "chiuso_da": st.column_config.TextColumn("Chiuso da"),
        },
    )

    # --------------------------------------------------------
    # ESPORTAZIONE
    # --------------------------------------------------------
    st.markdown("### 📥 Esportazione")
    excel_bytes = _excel_bytes(report_df)
    st.download_button(
        "📊 Esporta report filtrato in Excel",
        data=excel_bytes,
        file_name="report_ticket_filtrato.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

def _excel_bytes(df):
    output = BytesIO()
    export_df = df.copy()

    preferred = [
        "id", "titolo", "descrizione", "categoria", "priorita",
        "stato", "assegnato_a", "creato_da", "data_chiusura", "chiuso_da"
    ]
    ordered = [c for c in preferred if c in export_df.columns]
    ordered += [c for c in export_df.columns if c not in ordered]
    export_df = export_df[ordered]

    for col in ["data_chiusura"]:
        if col in export_df.columns:
            export_df[col] = export_df[col].apply(db.format_data)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Ticket")
        ws = writer.book["Ticket"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 12), 45)
    return output.getvalue()


def pagina_amministrazione():
    if not is_admin():
        st.error("Accesso non autorizzato.")
        return

    st.title("⚙️ Amministrazione")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["👥 Utenti", "🔐 Password", "🗂️ Categorie", "🗑️ Elimina ticket", "✍️ Firma amministratore"]
    )

    with tab1:
        st.subheader("Utenti")
        utenti = db.get_utenti()
        if utenti:
            df_utenti = pd.DataFrame(utenti)
            st.dataframe(
                df_utenti,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "username": st.column_config.TextColumn(
                        "Username", help="Nome utente per il login"
                    ),
                    "ruolo": st.column_config.TextColumn("Ruolo di Sistema"),
                    "attivo": st.column_config.CheckboxColumn(
                        "Stato Attivo", help="Indica se l'utente può accedere"
                    ),
                }
            )

        with st.expander("➕ Crea nuovo utente"):
            with st.form("crea_utente"):
                username = st.text_input("Username")
                ruolo = st.selectbox("Ruolo", ["Tecnico", "Amministratore"])
                password = st.text_input("Password iniziale", type="password")
                conferma = st.text_input("Conferma password", type="password")
                attivo = st.checkbox("Utente attivo", value=True)
                crea = st.form_submit_button("Crea utente", use_container_width=True)

            if crea:
                username = username.strip().lower()
                if not username:
                    st.error("Username obbligatorio.")
                elif password != conferma:
                    st.error("Le password non coincidono.")
                else:
                    ok, msg = auth.password_valida(password)
                    if not ok:
                        st.error(msg)
                    elif db.get_utente(username):
                        st.error("Username già esistente.")
                    else:
                        try:
                            db.crea_utente(
                                username,
                                auth.hash_password(password),
                                ruolo,
                                attivo
                            )
                            st.success("Utente creato.")
                            st.rerun()
                        except Exception as e:
                            st.error("Errore nella creazione dell'utente.")
                            st.exception(e)

        st.subheader("Gestione utenti")
        for user in utenti:
            username = user["username"]
            with st.expander(f"{username} — {user.get('ruolo', '')}"):
                new_role = st.selectbox(
                    "Ruolo",
                    ["Tecnico", "Amministratore"],
                    index=0 if str(user.get("ruolo", "")).lower() == "tecnico" else 1,
                    key=f"role_{username}",
                )
                new_active = st.checkbox(
                    "Attivo",
                    value=user.get("attivo", True) is not False,
                    key=f"active_{username}",
                )
                col1, col2 = st.columns(2)
                if col1.button(
                    "💾 Salva",
                    key=f"user_save_{username}",
                    use_container_width=True
                ):
                    try:
                        if username == st.session_state.username and not new_active:
                            st.error("Non puoi disattivare il tuo stesso account.")
                        else:
                            db.aggiorna_utente(
                                username,
                                ruolo=new_role,
                                attivo=new_active
                            )
                            st.success("Utente aggiornato.")
                            st.rerun()
                    except Exception as e:
                        st.error("Errore aggiornamento utente.")
                        st.exception(e)

                new_password = col2.text_input(
                    "Nuova password",
                    type="password",
                    key=f"newpw_{username}",
                )
                if st.button(
                    "🔑 Imposta password",
                    key=f"setpw_{username}",
                    use_container_width=True
                ):
                    ok, msg = auth.password_valida(new_password)
                    if not ok:
                        st.error(msg)
                    else:
                        db.aggiorna_utente(
                            username,
                            password=auth.hash_password(new_password)
                        )
                        st.success("Password aggiornata.")
                        st.rerun()

    with tab2:
        st.subheader("🔐 Cambia la tua password")
        auth.mostra_regole_password()
        with st.form("change_my_password"):
            old = st.text_input("Password attuale", type="password")
            new = st.text_input("Nuova password", type="password")
            confirm = st.text_input("Conferma nuova password", type="password")
            change = st.form_submit_button(
                "🔄 Cambia password",
                use_container_width=True
            )

        if change:
            current_user = db.get_utente(st.session_state.username)
            if not current_user or not auth.verifica_password(
                old, current_user.get("password", "")
            ):
                st.error("La password attuale non è corretta.")
            elif new != confirm:
                st.error("Le nuove password non coincidono.")
            elif old == new:
                st.error("La nuova password deve essere diversa da quella attuale.")
            else:
                ok, msg = auth.password_valida(new)
                if not ok:
                    st.error(msg)
                else:
                    db.aggiorna_utente(
                        st.session_state.username,
                        password=auth.hash_password(new),
                    )
                    st.success("Password modificata correttamente.")

    with tab3:
        st.subheader("🗂️ Categorie")
        categorie = db.get_categorie()
        if categorie:
            df_cat = pd.DataFrame(categorie)
            st.dataframe(
                df_cat,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "nome": st.column_config.TextColumn("Nome Categoria"),
                    "attivo": st.column_config.CheckboxColumn("Attiva"),
                }
            )

        with st.form("nuova_categoria"):
            nome = st.text_input("Nuova categoria")
            add = st.form_submit_button(
                "➕ Aggiungi categoria",
                use_container_width=True
            )

        if add:
            ok, msg = db.aggiungi_categoria(nome)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

        for cat in categorie:
            cid = cat["id"]
            with st.expander(f"{cat.get('nome', '')}"):
                new_name = st.text_input(
                    "Nome",
                    value=cat.get("nome", ""),
                    key=f"cat_name_{cid}",
                )
                active = st.checkbox(
                    "Attiva",
                    value=cat.get("attivo", True) is not False,
                    key=f"cat_active_{cid}",
                )
                if st.button(
                    "💾 Salva categoria",
                    key=f"cat_save_{cid}",
                    use_container_width=True
                ):
                    ok, msg = db.modifica_categoria(cid, new_name)
                    if ok:
                        db.cambia_stato_categoria(cid, active)
                        st.success("Categoria aggiornata.")
                        st.rerun()
                    else:
                        st.error(msg)

    with tab4:
        st.subheader("🗑️ Elimina ticket")
        st.warning(
            "L'eliminazione di un ticket è definitiva e rimuove anche interventi, "
            "messaggi, allegati, foto e firme collegati al ticket."
        )

        tickets = db.get_tickets()
        if not tickets:
            st.info("Non ci sono ticket da eliminare.")
        else:
            opzioni = []
            mappa = {}
            for t in tickets:
                tid = t.get("id")
                titolo = str(t.get("titolo") or "Senza titolo")
                stato = str(t.get("stato") or "")
                label = f"#{tid} — {titolo} — {stato}"
                opzioni.append(label)
                mappa[label] = tid

            # Nessun ticket viene selezionato automaticamente all'apertura
            # o dopo l'eliminazione di un ticket.
            placeholder = "— Seleziona un ticket —"
            scelta = st.selectbox(
                "Seleziona il ticket da eliminare",
                [placeholder] + opzioni,
                index=0,
                key="admin_delete_ticket_select",
            )

            if scelta == placeholder:
                st.info("Seleziona un ticket dall'elenco per procedere con l'eliminazione.")
            else:
                ticket_id = mappa[scelta]
                ticket = next((t for t in tickets if t.get("id") == ticket_id), None)
                if ticket:
                    st.markdown(
                        f"**Ticket #{ticket_id}**  \n"
                        f"Titolo: **{ticket.get('titolo') or 'Senza titolo'}**  \n"
                        f"Stato: **{ticket.get('stato') or '—'}**"
                    )

                conferma = st.checkbox(
                    "Confermo di voler eliminare definitivamente questo ticket",
                    key="admin_delete_ticket_confirm",
                )

                if st.button(
                    "🗑️ Elimina definitivamente il ticket",
                    type="primary",
                    disabled=not conferma,
                    use_container_width=True,
                    key="admin_delete_ticket_button",
                ):
                    if db.elimina_ticket_completo(ticket_id):
                        st.success(f"Ticket #{ticket_id} eliminato definitivamente.")
                        st.rerun()
                    else:
                        st.error("Il ticket non è stato eliminato.")

    with tab5:
        st.subheader("✍️ Firma amministratore")
        st.caption(
            "Carica la firma che verrà inserita automaticamente nel PDF "
            "quando questo amministratore chiude un ticket."
        )

        firma_esistente = db.scarica_firma_amministratore(
            st.session_state.username
        )
        if firma_esistente:
            st.image(
                firma_esistente,
                caption="Firma attualmente configurata",
                width=350,
            )
        else:
            st.info("Nessuna firma configurata per il tuo account amministratore.")

        firma_file = st.file_uploader(
            "Carica firma",
            type=["png", "jpg", "jpeg"],
            key="firma_amministratore_upload",
            help="Preferibilmente PNG con sfondo trasparente.",
        )

        if firma_file is not None:
            try:
                immagine = Image.open(firma_file)
                st.image(
                    immagine,
                    caption="Anteprima nuova firma",
                    width=350,
                )
            except Exception:
                st.error("Il file selezionato non è un'immagine valida.")
                firma_file = None

        if st.button(
            "💾 Salva firma amministratore",
            key="salva_firma_amministratore",
            use_container_width=True,
        ):
            if firma_file is None:
                st.warning("Seleziona prima un'immagine della firma.")
            else:
                try:
                    immagine = Image.open(firma_file)
                    if immagine.mode not in ("RGB", "RGBA"):
                        immagine = immagine.convert("RGBA")
                    buffer = BytesIO()
                    immagine.save(buffer, format="PNG")
                    db.salva_firma_amministratore(
                        st.session_state.username,
                        buffer.getvalue(),
                    )
                    st.success("✅ Firma amministratore salvata correttamente.")
                    st.rerun()
                except Exception as e:
                    st.error("Errore nel salvataggio della firma.")
                    st.exception(e)
