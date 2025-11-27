"""Models package."""

# We intentionally avoid eagerly importing submodules here.
#
# Previous versions pulled every model into the package namespace on import.
# That approach made importing *any* models submodule fail if optional
# dependencies (like ``email-validator`` for ``EmailStr`` fields) were
# missing. The Flask app imports :mod:`models.graph_state` during startup, so
# the eager imports could surface unrelated dependency errors as 500s when
# initializing the web server.

__all__ = []
