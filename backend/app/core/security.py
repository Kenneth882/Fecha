from passlib.context import CryptContext

_passwords = CryptContext(schemes=["argon2"])


def hash_password(password: str) -> str:
    """An argon2 hash of `password`, salted. CPU-heavy: call it off the event loop."""
    return _passwords.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Whether `password` matches `password_hash`. CPU-heavy, like hashing."""
    return _passwords.verify(password, password_hash)
