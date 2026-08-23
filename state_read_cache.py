from __future__ import annotations

import threading
import time
from typing import Any

from flask import Response, request

_ENDPOINT = "system_routes.get_state"
_TTL_SECONDS = 0.250

_lock = threading.Condition(threading.RLock())
_cached: tuple[float, int, bytes, list[tuple[str, str]]] | None = None
_building = False
_original = None


def invalidate_state_read_cache() -> None:
    global _cached
    with _lock:
        _cached = None
        _lock.notify_all()


def _clone_response(snapshot: tuple[float, int, bytes, list[tuple[str, str]]]) -> Response:
    _, status, body, headers = snapshot
    response = Response(body, status=status)
    for key, value in headers:
        lk = key.lower()
        if lk not in {"content-length", "connection", "transfer-encoding"}:
            response.headers[key] = value
    response.headers["Content-Length"] = str(len(body))
    response.headers["X-CSRN-State-Cache"] = "HIT"
    return response


def _snapshot_response(response: Response) -> tuple[float, int, bytes, list[tuple[str, str]]]:
    body = response.get_data()
    headers = list(response.headers.items())
    return (time.monotonic(), int(response.status_code), body, headers)


def install_state_read_cache(app: Any) -> None:
    global _original
    if getattr(app, "_csrn_state_read_cache_installed", False):
        return

    original = app.view_functions.get(_ENDPOINT)
    if original is None:
        raise RuntimeError(f"Expected Flask endpoint {_ENDPOINT!r} was not registered.")

    _original = original

    def cached_get_state(*args: Any, **kwargs: Any):
        global _cached, _building

        # GET/HEAD only. Mutation routes are untouched.
        if request.method not in {"GET", "HEAD"}:
            return original(*args, **kwargs)

        now = time.monotonic()
        with _lock:
            if _cached is not None and (now - _cached[0]) <= _TTL_SECONDS:
                return _clone_response(_cached)

            # If another worker is already constructing the same expensive
            # public-state snapshot, wait for it instead of duplicating the
            # 4 MB deep-copy/reconciliation work.
            if _building:
                deadline = now + 3.0
                while _building:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    _lock.wait(timeout=remaining)

                now = time.monotonic()
                if _cached is not None and (now - _cached[0]) <= _TTL_SECONDS:
                    return _clone_response(_cached)

            _building = True

        try:
            response = app.make_response(original(*args, **kwargs))
            if response.status_code == 200:
                snapshot = _snapshot_response(response)
                with _lock:
                    _cached = snapshot
            response.headers["X-CSRN-State-Cache"] = "MISS"
            return response
        finally:
            with _lock:
                _building = False
                _lock.notify_all()

    cached_get_state.__name__ = getattr(original, "__name__", "get_state")
    cached_get_state.__doc__ = getattr(original, "__doc__", None)
    cached_get_state.__module__ = getattr(original, "__module__", __name__)

    app.view_functions[_ENDPOINT] = cached_get_state
    app._csrn_state_read_cache_installed = True
