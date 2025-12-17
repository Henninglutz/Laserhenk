"""API Blueprint - Chat und Session Management."""

import asyncio
import logging
import uuid
from typing import Dict

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from pydantic import ValidationError

from app.middleware import get_current_user_id, jwt_required_optional
from workflow.graph_state import HenkGraphState, create_initial_state
from workflow.nodes_kiss import TOOL_REGISTRY
from workflow.workflow import create_smart_workflow

api_bp = Blueprint('api', __name__)

# Global workflow und sessions
_workflow = create_smart_workflow()
_sessions: Dict[str, HenkGraphState] = {}
_workflow_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_workflow_loop)


def _normalize_role(role: str | None) -> str:
    if role in {"ai", "assistant", "system"}:
        return "assistant"
    if role in {"human", "user"}:
        return "user"
    return "assistant" if role is None else role


def _message_to_dict(msg: dict) -> dict:
    if isinstance(msg, dict):
        role = _normalize_role(msg.get("role"))
        return {**msg, "role": role}

    role = _normalize_role(getattr(msg, "role", None) or getattr(msg, "type", None))
    content = getattr(msg, "content", "")
    data = {"role": role, "content": content}

    metadata = getattr(msg, "metadata", None) or getattr(msg, "additional_kwargs", None)
    if metadata:
        data["metadata"] = metadata

    sender = getattr(msg, "sender", None) or getattr(msg, "name", None)
    if sender:
        data["sender"] = sender

    return data


def _get_or_create_session(session_id: str = None, user_id: str = None) -> tuple[str, HenkGraphState]:
    """
    Hole oder erstelle Session.

    Args:
        session_id: Optional Session ID
        user_id: Optional User ID (für authenticated users)

    Returns:
        Tuple (session_id, state)
    """
    if session_id and session_id in _sessions:
        state = _sessions[session_id]
        # Setze user_id wenn authenticated
        if user_id and 'user_id' not in state:
            state['user_id'] = user_id
        return session_id, state

    # Neue Session erstellen
    new_sid = session_id or str(uuid.uuid4())
    new_state = create_initial_state(new_sid)

    if user_id:
        new_state['user_id'] = user_id

    _sessions[new_sid] = new_state
    return new_sid, new_state


@api_bp.route('/session', methods=['POST'])
@jwt_required_optional
def create_session():
    """
    Erstelle neue Session.

    Optional:
        - JWT Token für authenticated user

    Returns:
        201: Session ID
    """
    user_id = get_current_user_id()
    session_id, _ = _get_or_create_session(user_id=user_id)

    return jsonify({
        'session_id': session_id,
        'authenticated': user_id is not None,
    }), 201


@api_bp.route('/chat', methods=['POST'])
@jwt_required_optional
def chat():
    """
    Chat Endpoint - verarbeite User-Nachricht.

    Body:
        - message: str (required)
        - session_id: str (optional)

    Optional:
        - JWT Token für authenticated user

    Returns:
        200: Assistant response
        400: Validation error
    """
    try:
        data = request.get_json()
        message = str(data.get('message', '')).strip()

        if not message:
            return jsonify({'error': 'Nachricht darf nicht leer sein'}), 400

        session_id = data.get('session_id')
        user_id = get_current_user_id()

        # Get or create session
        sid, state = _get_or_create_session(session_id=session_id, user_id=user_id)

        # Add user message to history
        history = list(state.get('messages', []))
        history.append({
            'role': 'user',
            'content': message,
            'sender': 'user',
        })

        state['messages'] = history
        state['user_input'] = message

        # Process with workflow on a persistent event loop to avoid teardown issues
        logging.info("[API] Invoking workflow...")
        final_state = _workflow_loop.run_until_complete(_workflow.ainvoke(state))
        logging.info(f"[API] Workflow completed, got {len(final_state.get('messages', []))} messages")

        messages = [_message_to_dict(m) for m in final_state.get('messages', [])]
        logging.info(f"[API] Converted {len(messages)} messages to dict")

        final_state['messages'] = messages
        _sessions[sid] = final_state
        logging.info(f"[API] Saved session state")

        # Extract assistant reply, image_url, and fabric_images
        reply = 'Danke, ich habe alles notiert.'
        image_url = None
        fabric_images = None
        logging.info(f"[API] Starting metadata extraction from {len(messages)} messages")

        tool_senders = set(TOOL_REGISTRY.keys())

        # Prefer the latest agent reply (not a tool), but still capture tool metadata
        for msg in reversed(messages):
            if msg.get('role') != 'assistant':
                continue

            metadata = msg.get('metadata', {})
            sender = msg.get('sender', 'unknown')

            # DEBUG: Log metadata extraction
            if metadata:
                logging.info(f"[API] Message from {sender}: has metadata keys={list(metadata.keys())}")
                # DEBUG: Log actual metadata content
                logging.info(f"[API] Metadata content: {metadata}")

            if 'fabric_images' in metadata and not fabric_images:
                fabric_images = metadata['fabric_images']
                logging.info(f"[API] ✅ Extracted fabric_images from {sender}: {len(fabric_images)} images")
            if 'image_url' in metadata and not image_url:
                image_url = metadata['image_url']
                logging.info(f"[API] ✅ Extracted image_url from {sender}")

            if msg.get('sender') in tool_senders:
                continue

            reply = msg.get('content', reply)
            break

        # Current stage
        stage = final_state.get('current_agent') or final_state.get('next_agent') or 'henk1'

        response_data = {
            'reply': reply,
            'session_id': sid,
            'stage': stage,
            'authenticated': user_id is not None,
            'messages': messages,
        }

        # Add image_url if present
        if image_url:
            response_data['image_url'] = image_url

        # Add fabric_images if present
        if fabric_images:
            response_data['fabric_images'] = fabric_images

        return jsonify(response_data), 200

    except ValidationError as e:
        logging.error(f"[API] Validation error: {e}", exc_info=True)
        return jsonify({'error': 'Validation error', 'details': e.errors()}), 400
    except Exception as e:
        logging.error(f"[API] Internal error: {e}", exc_info=True)
        return jsonify({'error': 'Internal error', 'message': str(e)}), 500


@api_bp.route('/sessions', methods=['GET'])
@jwt_required()
def list_sessions():
    """
    Liste alle Sessions für den aktuellen User.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        200: Liste von Sessions
    """
    user_id = get_current_user_id()

    user_sessions = []
    for sid, state in _sessions.items():
        if state.get('user_id') == user_id:
            user_sessions.append({
                'session_id': sid,
                'current_agent': state.get('current_agent'),
                'message_count': len(state.get('messages', [])),
            })

    return jsonify({'sessions': user_sessions}), 200


@api_bp.route('/session/<session_id>', methods=['GET'])
@jwt_required_optional
def get_session(session_id: str):
    """
    Hole Session-Details.

    Args:
        session_id: Session ID

    Returns:
        200: Session state
        404: Session not found
        403: Unauthorized (wenn Session zu anderem User gehört)
    """
    if session_id not in _sessions:
        return jsonify({'error': 'Session nicht gefunden'}), 404

    state = _sessions[session_id]
    user_id = get_current_user_id()

    # Check authorization (wenn Session authenticated ist)
    session_user_id = state.get('user_id')
    if session_user_id and session_user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    return jsonify({
        'session_id': session_id,
        'current_agent': state.get('current_agent'),
        'messages': state.get('messages', []),
        'authenticated': session_user_id is not None,
    }), 200


@api_bp.route('/session/<session_id>', methods=['DELETE'])
@jwt_required_optional
def delete_session(session_id: str):
    """
    Lösche Session.

    Args:
        session_id: Session ID

    Returns:
        204: Session gelöscht
        404: Session not found
        403: Unauthorized
    """
    if session_id not in _sessions:
        return jsonify({'error': 'Session nicht gefunden'}), 404

    state = _sessions[session_id]
    user_id = get_current_user_id()

    # Check authorization
    session_user_id = state.get('user_id')
    if session_user_id and session_user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    del _sessions[session_id]
    return '', 204


@api_bp.route('/session/<session_id>/approve-image', methods=['POST'])
@jwt_required_optional
def approve_image(session_id: str):
    """
    Bestätige ein generiertes Bild.

    Args:
        session_id: Session ID

    Body:
        - image_url: str (required)
        - image_type: str (optional, default: "outfit_visualization")

    Returns:
        200: Image approved successfully
        400: Invalid request
        404: Session not found
    """
    if session_id not in _sessions:
        return jsonify({'error': 'Session nicht gefunden'}), 404

    try:
        data = request.get_json()
        image_url = data.get('image_url')

        if not image_url:
            return jsonify({'error': 'image_url is required'}), 400

        image_type = data.get('image_type', 'outfit_visualization')

        # Get session state
        state = _sessions[session_id]
        from models.customer import SessionState
        session_state = state.get('session_state')
        if isinstance(session_state, dict):
            session_state = SessionState(**session_state)

        # Approve image using storage manager
        import asyncio
        from tools.image_storage import get_storage_manager

        storage = get_storage_manager()
        success = asyncio.run(storage.approve_image(
            session_state=session_state,
            image_url=image_url,
            image_type=image_type,
        ))

        # Archive to session docs
        if success:
            asyncio.run(storage.archive_to_session_docs(
                session_id=session_id,
                image_url=image_url,
            ))

        # Update session state
        state['session_state'] = session_state
        _sessions[session_id] = state

        return jsonify({
            'success': success,
            'approved_image': image_url,
            'message': 'Bild wurde bestätigt und archiviert',
        }), 200

    except Exception as e:
        return jsonify({'error': 'Internal error', 'message': str(e)}), 500
