"""Minimaler HTTP-Server für den LASERHENK Browser-Chat."""

import asyncio
import json
import os
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from workflow.graph_state import HenkGraphState, create_initial_state
from workflow.workflow import create_smart_workflow

STATIC_ROOT = Path(__file__).parent / "templates"

_workflow = create_smart_workflow()
_sessions: Dict[str, HenkGraphState] = {}


def _message_to_dict(msg: dict) -> dict:
    if isinstance(msg, dict):
        return msg

    role = getattr(msg, "role", None) or getattr(msg, "type", None) or "assistant"
    content = getattr(msg, "content", "")
    data = {"role": role, "content": content}

    metadata = getattr(msg, "metadata", None) or getattr(msg, "additional_kwargs", None)
    if metadata:
        data["metadata"] = metadata

    sender = getattr(msg, "sender", None) or getattr(msg, "name", None)
    if sender:
        data["sender"] = sender

    return data


def _get_session(session_id: Optional[str]) -> Tuple[str, HenkGraphState]:
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]

    sid = session_id or str(uuid.uuid4())
    _sessions[sid] = create_initial_state(sid)
    return sid, _sessions[sid]


def process_chat(message: str, session_id: Optional[str] = None) -> Dict[str, object]:
    sid, state = _get_session(session_id)

    history = list(state.get("messages", []))
    history.append({"role": "user", "content": message, "sender": "user"})
    state["messages"] = history
    state["user_input"] = message

    final_state = asyncio.run(_workflow.ainvoke(state))
    messages = [_message_to_dict(m) for m in final_state.get("messages", [])]
    final_state["messages"] = messages
    _sessions[sid] = final_state

    reply = "Danke, ich habe alles notiert."
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            reply = msg.get("content", reply)
            break

    stage = final_state.get("current_agent") or final_state.get("next_agent") or "henk1"

    return {
        "reply": reply,
        "session_id": sid,
        "stage": stage,
        "messages": messages,
    }


class HenkRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            payload = {"status": "ok", "sessions": len(_sessions)}
            self._set_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        # Default: statische Dateien / index.html
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "Ungültiges JSON"}).encode("utf-8"))
            return

        if self.path == "/api/chat":
            message = str(payload.get("message", "")).strip()
            if not message:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Nachricht darf nicht leer sein"}).encode("utf-8"))
                return

            session_id = payload.get("session_id")
            response = process_chat(message, session_id=session_id)
            self._set_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        if self.path == "/api/session":
            sid, _ = _get_session(None)
            self._set_headers()
            self.wfile.write(json.dumps({"session_id": sid}).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))


def create_http_server(host: str = "0.0.0.0", port: int = 8000) -> ThreadingHTTPServer:
    """Erzeuge einen HTTP-Server für Browser-Tests oder CLI-Start."""
    return ThreadingHTTPServer((host, port), HenkRequestHandler)


def run(host: str = "0.0.0.0", port: int = 8000):
    with create_http_server(host, port) as httpd:
        print(f"🌐 Browser-Chat läuft auf http://{host}:{port}")
        print("Drücke STRG+C zum Stoppen.")
        httpd.serve_forever()


if __name__ == "__main__":
    run()
