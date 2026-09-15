"""Security and cryptographic utilities for password hashing and JWT token processing."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

pwd_context = PasswordHash((BcryptHasher(),))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain-text password against a bcrypt-hashed password string.

    Args:
        plain_password (str): Plain text secret to check.
        hashed_password (str): Bcrypt hash string stored in database.

    Returns:
        bool: True if password matches the hash, False otherwise.

    Example:
        >>> h = get_password_hash("Secret123")
        >>> verify_password("Secret123", h)
        True
        >>> verify_password("WrongPassword", h)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Computes a secure bcrypt hash of the provided password string.

    Args:
        password (str): Plain text password to hash.

    Returns:
        str: Bcrypt-hashed password string.

    Example:
        >>> h = get_password_hash("TestPass456")
        >>> h.startswith("$2")
        True
    """
    return pwd_context.hash(password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Generates a signed JWT access token for user authentication.

    Args:
        subject (str): Unique subject claim (typically user UUID).
        expires_delta (timedelta | None, optional): Custom lifespan duration. Defaults to None.

    Returns:
        str: Encoded JWT access token string.

    Example:
        >>> token = create_access_token("user-123")
        >>> len(token.split("."))
        3
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(seconds=settings.JWT_ACCESS_EXPIRES_IN)

    to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.JWT_ACCESS_SECRET, algorithm="HS256")


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Generates a signed JWT refresh token for session maintenance.

    Args:
        subject (str): Unique subject claim (typically user UUID).
        expires_delta (timedelta | None, optional): Custom lifespan duration. Defaults to None.

    Returns:
        str: Encoded JWT refresh token string.

    Example:
        >>> token = create_refresh_token("user-123")
        >>> len(token.split("."))
        3
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(seconds=settings.JWT_REFRESH_EXPIRES_IN)

    to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.JWT_REFRESH_SECRET, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict[str, Any] | None:
    """Decodes and validates a JWT token using the specified HMAC secret.

    Args:
        token (str): Encoded JWT token string.
        secret (str): HMAC secret key used for signing.

    Returns:
        dict[str, Any] | None: Decoded claims mapping if valid; None if expired or invalid.

    Example:
        >>> token = create_access_token("test-sub")
        >>> claims = decode_token(token, settings.JWT_ACCESS_SECRET)
        >>> claims["sub"]
        'test-sub'
    """
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        return None
