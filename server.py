"""Forward-compatible server entrypoint for chat endpoints."""

from server_old import create_http_server, process_chat, run

__all__ = ["create_http_server", "process_chat", "run"]
