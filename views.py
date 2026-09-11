import base64
from io import BytesIO
from datetime import date

import pandas as pd
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


def pagina_login():
    st.title("🎫 Gestione Ticket")
    st.subheader("Accesso")

    with st.form("login_form"):
        username = st.text_input("Utente")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("🔐 Accedi", use_container_width=True)

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

        # Migrazione automatica di eventuali vecchie password in chiaro.
        if "$" not in str(user.get("password", "")):
            db.aggiorna_utente(username, password=auth.hash_password(password))

        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.ruolo = user.get("ruolo", "")
        st.rerun()


def pagina_dashboard():
    st.title("📊 Dashboard")

    admin = is_admin()
    username = st.session_state.username

    rows = db.get_tickets() if admin else db.get_tickets_tecnico(username)

    if not rows:
        st.info("Non ci sono ticket da visualizzare.")
        return

    df = pd.DataFrame(rows)

    st.subheader("Filtri")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        cerca = st.text_input("🔎 Cerca", placeholder="Titolo, descrizione o categoria")
    with c2:
        stato = st.selectbox("Stato", ["Tutti"] + STATI)
    with c3:
        priorita = st.selectbox("Priorità", ["Tutte"] + PRIORITA)
    with c4:
        if admin:
            assegnati = sorted(
                [x for x in df.get("assegnato_a", pd.Series(dtype=str)).dropna().unique() if str(x).strip()]
            )
            assegnato = st.selectbox("Assegnato a", ["Tutti"] + assegnati)
        else:
            assegnato = "Tutti"

    filtrato = df.copy()

    if cerca:
        mask = (
            filtrato.astype(str)
            .apply(lambda col: col.str.contains(cerca, case=False, na=False))
            .any(axis=1)
        )
        filtrato = filtrato[mask]

    if stato != "Tutti":
        filtrato = filtrato[filtrato["stato"] == stato]

    if priorita != "Tutte":
        filtrato = filtrato[filtrato["priorita"] == priorita]

    if admin and assegnato != "Tutti":
        filtrato = filtrato[filtrato["assegnato_a"] == assegnato]

    st.write(f"**Ticket visualizzati: {len(filtrato)}**")

    for _, row in filtrato.iterrows():
        ticket_id = int(row["id"])
        label = f"#{ticket_id} — {_safe(row.get('titolo'))} — {_safe(row.get('stato'))}"

        with st.expander(label):
            a, b, c, d = st.columns(4)
            a.metric("Stato", _safe(row.get("stato")))
            b.metric("Priorità", _safe(row.get("priorita")))
            c.metric("Categoria", _safe(row.get("categoria")))
            d.metric("Tecnico", _safe(row.get("assegnato_a")))

            st.write(_safe(row.get("descrizione")))

            if st.button("Apri ticket", key=f"open_{ticket_id}"):
                st.session_state[f"ticket_aperto_{ticket_id}"] = True

            if st.session_state.get(f"ticket_aperto_{ticket_id}"):
                mostra_dettaglio_ticket(ticket_id)


def pagina_nuovo_ticket():
    st.title("➕ Nuovo Ticket")

    categorie = db.get_nomi_categorie_attive()
    tecnici = db.get_tecnici_attivi()

    if not categorie:
        st.warning("Non ci sono categorie attive. Un amministratore deve crearne almeno una.")
        return
    if not tecnici:
        st.warning("Non ci sono tecnici attivi.")
        return

    with st.form("nuovo_ticket_form", clear_on_submit=True):
        titolo = st.text_input("Titolo")
        descrizione = st.text_area("Descrizione", height=150)
        c1, c2 = st.columns(2)
        categoria = c1.selectbox("Categoria", categorie)
        priorita = c2.selectbox("Priorità", PRIORITA)
        assegnato_a = st.selectbox("Assegnato a", tecnici)
        allegati = st.file_uploader(
            "📎 Allegati",
            type=["jpg", "jpeg", "png", "pdf", "doc", "docx", "xls", "xlsx", "txt"],
            accept_multiple_files=True,
        )
        foto = st.camera_input("📷 Foto del problema")
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

        st.success(f"Ticket #{ticket_id} creato correttamente.")
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
        path = allegato.get("percorso", "")
        mime = allegato.get("tipo_mime", "")

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
    if not canvas_result or not canvas_result.image_data is not None:
        return None
    image_data = canvas_result.image_data
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

    st.divider()
    st.header(f"🎫 Ticket #{ticket_id}: {_safe(ticket.get('titolo'))}")

    c1, c2, c3, c4 = st.columns(4)
    c1.write(f"**Stato:** {_safe(ticket.get('stato'))}")
    c2.write(f"**Priorità:** {_safe(ticket.get('priorita'))}")
    c3.write(f"**Categoria:** {_safe(ticket.get('categoria'))}")
    c4.write(f"**Tecnico:** {assegnato}")

    st.write(f"**Creato da:** {_safe(ticket.get('creato_da'))}")
    st.write(f"**Creato il:** {db.format_data(ticket.get('creato_il'))}")
    st.write(f"**Modificato il:** {db.format_data(ticket.get('modificato_il'))}")
    st.markdown("### Descrizione")
    st.write(_safe(ticket.get("descrizione")))

    _mostra_allegati(ticket_id)

    intervento = db.get_intervento(ticket_id)

    if admin:
        st.markdown("### 🛠️ Intervento tecnico")
        tecnico = st.text_input("Tecnico", value=assegnato, disabled=True)
        stato_options = STATI
        stato = st.selectbox(
            "Stato",
            stato_options,
            index=stato_options.index(stato_attuale) if stato_attuale in stato_options else 0,
            key=f"admin_state_{ticket_id}",
        )
        note = st.text_area(
            "Note / intervento",
            value=_safe(intervento.get("descrizione_intervento") if intervento else ""),
            key=f"admin_note_{ticket_id}",
        )

        if st.button("💾 Salva intervento", key=f"admin_save_{ticket_id}"):
            try:
                db.supabase.table("ticket_interventi").upsert({
                    "ticket_id": ticket_id,
                    "tecnico": tecnico,
                    "descrizione_intervento": note,
                    "stato": stato,
                    "firma_path": intervento.get("firma_path") if intervento else None,
                    "modificato_il": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                }, on_conflict="ticket_id").execute()
                db.aggiorna_stato_ticket(ticket_id, stato)
                st.success("Intervento aggiornato.")
                st.rerun()
            except Exception as e:
                st.error("Errore nel salvataggio.")
                st.exception(e)

        if intervento and intervento.get("firma_path"):
            try:
                firma = db.scarica_firma_intervento(intervento["firma_path"])
                st.image(firma, caption="Firma del tecnico", width=350)
            except Exception:
                st.warning("Firma presente ma non visualizzabile.")

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
                )
            except Exception as e:
                st.error("Errore nella generazione PDF.")
                st.exception(e)

        with col_close:
            if stato_attuale != "Chiuso":
                if st.button("🔒 Chiudi ticket", key=f"close_{ticket_id}"):
                    db.aggiorna_stato_ticket(ticket_id, "Chiuso")
                    st.success("Ticket chiuso.")
                    st.rerun()

    else:
        st.markdown("### 🛠️ Intervento tecnico")

        if stato_attuale in {"Risolto", "Chiuso"}:
            st.success(f"Ticket {stato_attuale.lower()}: modifica non consentita.")
            if intervento:
                st.write(_safe(intervento.get("descrizione_intervento")))
            if intervento and intervento.get("firma_path"):
                try:
                    firma = db.scarica_firma_intervento(intervento["firma_path"])
                    st.image(firma, caption="Firma del tecnico", width=350)
                except Exception:
                    pass
            return

        stato_options = ["Aperto", "In Lavorazione", "Risolto"]
        stato = st.selectbox(
            "Stato",
            stato_options,
            index=stato_options.index(stato_attuale) if stato_attuale in stato_options else 0,
            key=f"tech_state_{ticket_id}",
        )
        note = st.text_area(
            "Note intervento",
            value=_safe(intervento.get("descrizione_intervento") if intervento else ""),
            key=f"tech_note_{ticket_id}",
        )

        canvas_result = None
        if stato == "Risolto":
            st.info("Per risolvere il ticket è richiesta la firma grafica del tecnico.")
            canvas_result = st_canvas(
                fill_color="rgba(255,255,255,0)",
                stroke_width=2,
                stroke_color="#000000",
                background_color="#FFFFFF",
                height=180,
                width=600,
                drawing_mode="freedraw",
                key=f"firma_{ticket_id}",
            )

        if st.button("💾 Salva intervento", key=f"tech_save_{ticket_id}"):
            try:
                firma_path = intervento.get("firma_path") if intervento else None
                if stato == "Risolto":
                    firma_bytes = _firma_da_canvas(canvas_result)
                    if not firma_bytes:
                        st.error("Inserisci la firma prima di risolvere il ticket.")
                        return
                    firma_path = db.salva_firma_intervento(
                        ticket_id, firma_bytes, f"firma_ticket_{ticket_id}.png"
                    )

                db.salva_intervento_tecnico(
                    ticket_id,
                    username,
                    note,
                    stato,
                    firma_path=firma_path,
                )
                st.success("Intervento salvato.")
                st.rerun()
            except PermissionError as e:
                st.error(str(e))
            except Exception as e:
                st.error("Errore nel salvataggio dell'intervento.")
                st.exception(e)


def pagina_statistiche():
    if not is_admin():
        st.error("Accesso non autorizzato.")
        return

    st.title("📈 Statistiche & Report")
    rows = db.get_tickets()
    df = pd.DataFrame(rows)

    if df.empty:
        st.info("Non ci sono dati.")
        return

    total = len(df)
    aperti = int((df["stato"] == "Aperto").sum())
    lavorazione = int((df["stato"] == "In Lavorazione").sum())
    risolti = int((df["stato"] == "Risolto").sum())
    chiusi = int((df["stato"] == "Chiuso").sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Totali", total)
    c2.metric("Aperti", aperti)
    c3.metric("In lavorazione", lavorazione)
    c4.metric("Risolti", risolti)
    c5.metric("Chiusi", chiusi)

    st.subheader("Ticket per stato")
    st.bar_chart(df["stato"].value_counts())

    if "priorita" in df.columns:
        st.subheader("Ticket per priorità")
        st.bar_chart(df["priorita"].value_counts())

    if "assegnato_a" in df.columns:
        st.subheader("Ticket per tecnico")
        st.bar_chart(df["assegnato_a"].fillna("Non assegnato").value_counts())

    st.subheader("📋 Dati")
    st.dataframe(df, use_container_width=True, hide_index=True)

    excel_bytes = _excel_bytes(df)
    st.download_button(
        "📊 Esporta in Excel",
        data=excel_bytes,
        file_name="report_ticket.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ticket")
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

    tab1, tab2, tab3 = st.tabs(["👥 Utenti", "🔐 Password", "🗂️ Categorie"])

    with tab1:
        st.subheader("Utenti")
        utenti = db.get_utenti()
        if utenti:
            st.dataframe(pd.DataFrame(utenti), use_container_width=True, hide_index=True)

        with st.expander("➕ Crea nuovo utente"):
            with st.form("crea_utente"):
                username = st.text_input("Username")
                ruolo = st.selectbox("Ruolo", ["Tecnico", "Amministratore"])
                password = st.text_input("Password iniziale", type="password")
                conferma = st.text_input("Conferma password", type="password")
                attivo = st.checkbox("Utente attivo", value=True)
                crea = st.form_submit_button("Crea utente")

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
                            db.crea_utente(username, auth.hash_password(password), ruolo, attivo)
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
                if col1.button("💾 Salva", key=f"user_save_{username}"):
                    try:
                        # Impedisce di disattivare il proprio account.
                        if username == st.session_state.username and not new_active:
                            st.error("Non puoi disattivare il tuo stesso account.")
                        else:
                            db.aggiorna_utente(username, ruolo=new_role, attivo=new_active)
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
                if st.button("🔑 Imposta password", key=f"setpw_{username}"):
                    ok, msg = auth.password_valida(new_password)
                    if not ok:
                        st.error(msg)
                    else:
                        db.aggiorna_utente(username, password=auth.hash_password(new_password))
                        st.success("Password aggiornata.")
                        st.rerun()

    with tab2:
        st.subheader("🔐 Cambia la tua password")
        auth.mostra_regole_password()
        with st.form("change_my_password"):
            old = st.text_input("Password attuale", type="password")
            new = st.text_input("Nuova password", type="password")
            confirm = st.text_input("Conferma nuova password", type="password")
            change = st.form_submit_button("🔄 Cambia password", use_container_width=True)

        if change:
            current_user = db.get_utente(st.session_state.username)
            if not current_user or not auth.verifica_password(old, current_user.get("password", "")):
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
            st.dataframe(pd.DataFrame(categorie), use_container_width=True, hide_index=True)

        with st.form("nuova_categoria"):
            nome = st.text_input("Nuova categoria")
            add = st.form_submit_button("➕ Aggiungi categoria")

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
                    value=cat.get("attiva", True) is not False,
                    key=f"cat_active_{cid}",
                )
                if st.button("💾 Salva categoria", key=f"cat_save_{cid}"):
                    ok, msg = db.modifica_categoria(cid, new_name)
                    if ok:
                        db.cambia_stato_categoria(cid, active)
                        st.success("Categoria aggiornata.")
                        st.rerun()
                    else:
                        st.error(msg)
