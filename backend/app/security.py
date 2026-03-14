import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def derive_fernet_key(secret: str) -> str:
    secret_bytes = secret.encode("utf-8")
    digest = hashlib.sha256(secret_bytes).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def _get_fernet(encryption_key: str) -> Fernet:
    return Fernet(encryption_key.encode("utf-8"))


def encrypt_secret(value: str, encryption_key: str) -> str:
    fernet = _get_fernet(encryption_key)
    encrypted = fernet.encrypt(value.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_secret(value: str, encryption_key: str) -> str:
    fernet = _get_fernet(encryption_key)
    decrypted = fernet.decrypt(value.encode("utf-8"))
    return decrypted.decode("utf-8")


def maybe_decrypt_secret(value: str, encryption_key: str) -> str:
    try:
        return decrypt_secret(value, encryption_key)
    except InvalidToken:
        return value
