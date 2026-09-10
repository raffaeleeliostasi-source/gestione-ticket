import hashlib
import hmac
import secrets
import re
import streamlit as st

def genera_hash_password(password):
    """Genera un hash PBKDF2-HMAC-SHA256 con salt casuale."""
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000
    )
    return f"{salt.hex()}${password_hash.hex()}"

def verifica_password(password, password_salvata):
    """Verifica la password con supporto a vecchi hash/plain-text."""
    if not password_salvata:
        return False

    if "$" in password_salvata:
        try:
            salt_hex, hash_salvato = password_salvata.split("$", 1)
            salt = bytes.fromhex(salt_hex)
            nuovo_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                200_000
            ).hex()
            return hmac.compare_digest(nuovo_hash, hash_salvato)
        except Exception:
            return False

    return hmac.compare_digest(password, password_salvata)

def password_da_migrare(password_salvata):
    return bool(password_salvata and "$" not in password_salvata)

def valida_password(password):
    errori = []
    if len(password) < 8:
        errori.append("Almeno 8 caratteri.")
    if not re.search(r"[A-Z]", password):
        errori.append("Almeno una lettera maiuscola.")
    if not re.search(r"[a-z]", password):
        errori.append("Almeno una lettera minuscola.")
    if not re.search(r"\d", password):
        errori.append("Almeno un numero.")
    return errori

def mostra_regole_password():
    st.caption("La password deve contenere almeno 8 caratteri, una maiuscola, una minuscola e un numero.")
