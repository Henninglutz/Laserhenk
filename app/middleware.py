"""Middleware für JWT Token Validation und User Context."""

from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from typing import Callable, Optional


def jwt_required_optional(fn: Callable) -> Callable:
    """
    JWT Optional Decorator - erlaubt sowohl authenticated als auch anonymous requests.

    Wenn Token vorhanden und valid: user_id wird gesetzt
    Wenn kein Token oder invalid: user_id = None (Anonymous)
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request(optional=True)
        except Exception:
            pass  # Ignore errors - allow anonymous

        return fn(*args, **kwargs)

    return wrapper


def beta_user_required(fn: Callable) -> Callable:
    """
    Decorator für Beta-User-Zugang.

    Prüft ob User im Token als beta_user markiert ist.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()

        claims = get_jwt()
        if not claims.get('is_beta_user', False):
            return jsonify({
                'error': 'Beta access required',
                'message': 'Diese Funktion ist nur für Beta-User verfügbar'
            }), 403

        return fn(*args, **kwargs)

    return wrapper


def get_current_user_id() -> Optional[str]:
    """
    Hole aktuelle User ID aus JWT Token.

    Returns:
        User ID oder None wenn nicht authenticated
    """
    try:
        return get_jwt_identity()
    except Exception:
        return None


def get_current_user_claims() -> dict:
    """
    Hole alle Claims aus JWT Token.

    Returns:
        Dict mit allen Claims oder leeres dict
    """
    try:
        return get_jwt()
    except Exception:
        return {}
