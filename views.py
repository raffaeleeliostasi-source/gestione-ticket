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
        /* Sfondo e contenitore principale della pagina di accesso */
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 82% 8%, rgba(180, 214, 255, .55) 0, rgba(180, 214, 255, 0) 34%),
                radial-gradient(circle at 8% 92%, rgba(191, 219, 254, .60) 0, rgba(191, 219, 254, 0) 35%),
                #F7FBFF;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        .login-page {
            position: relative;
            max-width: 580px;
            margin: 3.2rem auto 1.5rem auto;
        }

        .login-brand {
            background: rgba(255,255,255,.98);
            border-radius: 18px 18px 0 0;
            padding: 24px 28px 20px 28px;
            box-shadow: 0 12px 35px rgba(38, 91, 145, .10);
            text-align: left;
        }

        .login-brand-row {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 18px;
        }

        .login-butterfly {
            width: 76px;
            height: 94px;
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
            font-size: 2.75rem;
            line-height: .94;
            font-weight: 800;
            letter-spacing: -1.5px;
            color: #173B68;
        }

        .login-title .ticket {
            display: block;
            color: #B51F2B;
        }

        .login-subtitle {
            margin-top: 10px;
            color: #627B9D;
            font-size: 0.98rem;
            font-weight: 500;
        }

        .login-divider {
            height: 2px;
            background: #D5E6FA;
            margin-top: 20px;
            border-radius: 2px;
        }

        /* La card del form ridotta in larghezza e centrata */
        [data-testid="stForm"] {
            max-width: 580px;
            margin: 0 auto;
            background: rgba(255,255,255,.98);
            border: 0 !important;
            border-radius: 0 0 18px 18px !important;
            padding: 0 28px 26px 28px !important;
            box-shadow: 0 18px 35px rgba(38, 91, 145, .10);
        }

        .login-form-title {
            text-align: center;
            color: #173B68;
            font-size: 1.65rem;
            font-weight: 800;
            margin: 0 0 4px 0;
        }

        .login-form-subtitle {
            text-align: center;
            color: #6C84A5;
            font-size: 0.92rem;
            margin: 0 0 20px 0;
        }

        [data-testid="stForm"] label {
            color: #173B68 !important;
            font-weight: 700 !important;
        }

        [data-testid="stForm"] input {
            border: 1.5px solid #C9DCF2 !important;
            border-radius: 10px !important;
            min-height: 44px !important;
            background: #FFFFFF !important;
        }

        [data-testid="stForm"] input:focus {
            border-color: #B51F2B !important;
            box-shadow: 0 0 0 2px rgba(181,31,43,.10) !important;
        }

        /* ==========================================================
           CENTRAMENTO COMPLETO DEL PULSANTE ACCEDI
           ========================================================== */

        [data-testid="stFormSubmitButton"] {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            width: 100% !important;
            margin: 0 auto !important;
        }

        [data-testid="stFormSubmitButton"] > div {
            width: 100% !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            margin: 0 auto !important;
        }

        [data-testid="stFormSubmitButton"] button {
            display: block !important;
            margin: 12px auto 0 auto !important;
        }

        /* Pulsante ACCEDI */
        [data-testid="stForm"] button[kind="primaryFormSubmit"],
        [data-testid="stForm"] button[type="submit"] {
            display: block !important;
            margin: 12px auto 0 auto !important;
            width: 220px !important;
            min-height: 46px !important;
            border-radius: 6px !important;
            background: linear-gradient(180deg, #9C1C24, #7E1219) !important;
            border: none !important;
            color: white !important;
            font-weight: 900 !important;
            font-size: 1.1rem !important;
            letter-spacing: 1.2px !important;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.18) !important;
        }

        [data-testid="stForm"] button[type="submit"]:hover {
            background: linear-gradient(180deg, #7E1219, #600D12) !important;
        }

        @media (max-width: 640px) {
            .login-page {
                margin: 1rem auto .75rem auto;
                max-width: 100%;
            }

            .login-brand {
                border-radius: 16px 16px 0 0;
                padding: 20px 16px 16px 16px;
            }

            .login-brand-row {
                gap: 12px;
            }

            .login-butterfly {
                width: 60px;
                height: 74px;
            }

            .login-title {
                font-size: 1.95rem;
                letter-spacing: -1px;
            }

            .login-subtitle {
                font-size: .8rem;
                margin-top: 6px;
            }

            .login-divider {
                margin-top: 14px;
            }

            [data-testid="stForm"] {
                border-radius: 0 0 16px 16px !important;
                padding: 0 16px 18px 16px !important;
            }

            .login-form-title {
                font-size: 1.35rem;
            }

            .login-form-subtitle {
                font-size: .82rem;
                margin-bottom: 16px;
            }

            /* Anche su smartphone il pulsante rimane centrato */
            [data-testid="stFormSubmitButton"] {
                width: 100% !important;
                display: flex !important;
                justify-content: center !important;
                align-items: center !important;
            }

            [data-testid="stFormSubmitButton"] > div {
                width: 100% !important;
                display: flex !important;
                justify-content: center !important;
            }

            [data-testid="stFormSubmitButton"] button,
            [data-testid="stForm"] button[type="submit"] {
                width: 220px !important;
                max-width: 220px !important;
                margin-left: auto !important;
                margin-right: auto !important;
            }
        }
        </style>
        """,
        u
```
