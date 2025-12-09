import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import create_http_server, process_chat


def test_process_chat_creates_and_reuses_session():
    first = process_chat("Hallo HENK")
    assert first["session_id"]
    session_id = first["session_id"]

    second = process_chat("Ich brauche ein Sakko", session_id=session_id)
    assert second["session_id"] == session_id
    assert len(second.get("messages", [])) >= len(first.get("messages", []))


def test_http_server_endpoints():
    server = create_http_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)

    host, port = server.server_address

    conn = HTTPConnection(host, port)
    payload = json.dumps({"message": "Hallo aus dem Test"})
    conn.request("POST", "/api/chat", body=payload, headers={"Content-Type": "application/json"})
    res = conn.getresponse()
    assert res.status == 200
    data = json.loads(res.read())
    assert data.get("session_id")
    assert data.get("reply")

    conn.request("GET", "/health")
    health_res = conn.getresponse()
    assert health_res.status == 200

    server.shutdown()
    thread.join()
