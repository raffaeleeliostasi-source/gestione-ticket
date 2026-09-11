import hashlib
import hmac
import secrets
import streamlit as st

PBKDF2_ITERATIONS = 200_000
PASSWORD_MIN_LENGTH = 8


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{salt.hex()}${digest.hex()}"


def verifica_password(password: str, stored_password: str) -> bool:
    if not stored_password:
        return False

    # Compatibilità con eventuali vecchie password salvate in chiaro.
    if "$" not in stored_password:
        return hmac.compare_digest(password, stored_password)

    try:
        salt_hex, digest_hex = stored_password.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PBKDF2_ITERATIONS,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def password_valida(password: str) -> tuple[bool, str]:
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, "La password deve contenere almeno 8 caratteri."
    if not any(c.isupper() for c in password):
        return False, "La password deve contenere almeno una lettera maiuscola."
    if not any(c.islower() for c in password):
        return False, "La password deve contenere almeno una lettera minuscola."
    if not any(c.isdigit() for c in password):
        return False, "La password deve contenere almeno un numero."
    return True, ""


def mostra_regole_password():
    st.caption(
        "Password: almeno 8 caratteri, una maiuscola, una minuscola e un numero."
    )
