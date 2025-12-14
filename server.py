"""HTTP server entrypoint for the LASERHENK browser chat.

This module re-exports the existing server implementation so it can be
imported as ``server`` (e.g. by tests) while keeping the original logic
in ``server_old.py``.
"""

from server_old import HenkRequestHandler, create_http_server, process_chat, run


__all__ = [
    "HenkRequestHandler",
    "create_http_server",
    "process_chat",
    "run",
]


if __name__ == "__main__":
    run()
