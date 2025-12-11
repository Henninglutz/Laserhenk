"""Authentication Blueprint - Login, Register, JWT Token Management."""

import uuid
from datetime import datetime
from typing import Optional

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
)
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from pydantic import ValidationError

from models.auth import (
    User,
    UserCreate,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
)

auth_bp = Blueprint('auth', __name__)
ph = PasswordHasher()

# In-Memory User Store (für Development - später PostgreSQL)
# TODO: Migriere zu PostgreSQL mit users Table
_users_db = {}  # email -> User


def _find_user_by_email(email: str) -> Optional[User]:
    """Finde User by Email."""
    return _users_db.get(email.lower())


def _find_user_by_id(user_id: str) -> Optional[User]:
    """Finde User by ID."""
    for user in _users_db.values():
        if user.user_id == user_id:
            return user
    return None


def _save_user(user: User) -> None:
    """Speichere User."""
    _users_db[user.email.lower()] = user


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Registriere neuen User.

    Body:
        - email: str
        - username: str
        - password: str
        - is_beta_user: bool (optional, default False)

    Returns:
        201: User erstellt mit Tokens
        400: Validation Error
        409: Email bereits registriert
    """
    try:
        data = request.get_json()
        user_data = UserCreate(**data)
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.errors()}), 400

    # Check if user already exists
    if _find_user_by_email(user_data.email):
        return jsonify({'error': 'Email bereits registriert'}), 409

    # Hash password
    password_hash = ph.hash(user_data.password)

    # Create user
    user = User(
        user_id=str(uuid.uuid4()),
        email=user_data.email.lower(),
        username=user_data.username,
        password_hash=password_hash,
        is_active=True,
        is_beta_user=user_data.is_beta_user,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    _save_user(user)

    # Generate tokens
    access_token = create_access_token(
        identity=user.user_id,
        additional_claims={
            'email': user.email,
            'username': user.username,
            'is_beta_user': user.is_beta_user,
        }
    )
    refresh_token = create_refresh_token(identity=user.user_id)

    return jsonify({
        'message': 'User erfolgreich registriert',
        'user': {
            'user_id': user.user_id,
            'email': user.email,
            'username': user.username,
            'is_beta_user': user.is_beta_user,
        },
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer',
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login mit Email + Password.

    Body:
        - email: str
        - password: str

    Returns:
        200: Login successful mit Tokens
        400: Validation error
        401: Invalid credentials
    """
    try:
        data = request.get_json()
        login_req = LoginRequest(**data)
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.errors()}), 400

    # Find user
    user = _find_user_by_email(login_req.email)
    if not user:
        return jsonify({'error': 'Ungültige Email oder Passwort'}), 401

    # Verify password
    try:
        ph.verify(user.password_hash, login_req.password)
    except VerifyMismatchError:
        return jsonify({'error': 'Ungültige Email oder Passwort'}), 401

    # Check if account is active
    if not user.is_active:
        return jsonify({'error': 'Account ist deaktiviert'}), 401

    # Update last_login
    user.last_login = datetime.utcnow()
    _save_user(user)

    # Generate tokens
    access_token = create_access_token(
        identity=user.user_id,
        additional_claims={
            'email': user.email,
            'username': user.username,
            'is_beta_user': user.is_beta_user,
        }
    )
    refresh_token = create_refresh_token(identity=user.user_id)

    response = LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type='Bearer',
        user_id=user.user_id,
        email=user.email,
        username=user.username,
        is_beta_user=user.is_beta_user,
    )

    return jsonify(response.model_dump()), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh Access Token mit Refresh Token.

    Headers:
        Authorization: Bearer <refresh_token>

    Returns:
        200: Neuer Access Token
    """
    current_user_id = get_jwt_identity()
    user = _find_user_by_id(current_user_id)

    if not user:
        return jsonify({'error': 'User nicht gefunden'}), 404

    access_token = create_access_token(
        identity=user.user_id,
        additional_claims={
            'email': user.email,
            'username': user.username,
            'is_beta_user': user.is_beta_user,
        }
    )

    return jsonify({
        'access_token': access_token,
        'token_type': 'Bearer',
    }), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Hole aktuellen User aus JWT Token.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        200: User Info
        404: User nicht gefunden
    """
    current_user_id = get_jwt_identity()
    user = _find_user_by_id(current_user_id)

    if not user:
        return jsonify({'error': 'User nicht gefunden'}), 404

    return jsonify({
        'user_id': user.user_id,
        'email': user.email,
        'username': user.username,
        'is_beta_user': user.is_beta_user,
        'is_active': user.is_active,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'last_login': user.last_login.isoformat() if user.last_login else None,
    }), 200


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    Ändere Passwort für aktuellen User.

    Body:
        - current_password: str
        - new_password: str

    Returns:
        200: Passwort geändert
        400: Validation error
        401: Falsches aktuelles Passwort
    """
    try:
        data = request.get_json()
        pwd_change = PasswordChangeRequest(**data)
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.errors()}), 400

    current_user_id = get_jwt_identity()
    user = _find_user_by_id(current_user_id)

    if not user:
        return jsonify({'error': 'User nicht gefunden'}), 404

    # Verify current password
    try:
        ph.verify(user.password_hash, pwd_change.current_password)
    except VerifyMismatchError:
        return jsonify({'error': 'Aktuelles Passwort ist falsch'}), 401

    # Hash new password
    user.password_hash = ph.hash(pwd_change.new_password)
    user.updated_at = datetime.utcnow()
    _save_user(user)

    return jsonify({'message': 'Passwort erfolgreich geändert'}), 200
