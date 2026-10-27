"""
auth.py
Password hashing + remember-me token helpers for recruiter accounts. Uses
only the Python standard library (hashlib's PBKDF2-HMAC-SHA256, secrets)
so no extra pip install is required beyond what you already have.

Each password is stored as a random salt + a hash of (password + salt),
never the plain password itself. Remember-me tokens work the same way:
only a hash of the token is stored in the database, the raw token lives
in the browser's URL.
"""

import hashlib
import os
import secrets
import binascii
from typing import Tuple

PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
    """Returns (salt_hex, hash_hex). Pass salt=None when creating a new
    account (a random salt is generated); pass the stored salt back in
    when verifying an existing password."""
    if salt is None:
        salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return binascii.hexlify(salt).decode(), binascii.hexlify(pwd_hash).decode()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    """Re-hashes the given password with the stored salt and compares
    against the stored hash."""
    salt = binascii.unhexlify(salt_hex)
    _, computed_hash = hash_password(password, salt)
    return computed_hash == expected_hash_hex


def generate_remember_token() -> str:
    """A random, URL-safe token to store in the browser (via a query
    param) for 'remember me'. Only its hash ever touches the database."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """One-way hash of a remember-me token, safe to store in the DB."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

