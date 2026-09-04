"""Shared authorization helpers for web, analytics, and mobile routes."""
from functools import wraps
from collections import defaultdict, deque
from threading import Lock
import time

from flask import abort, request
from flask_login import current_user


VALID_ROLES = frozenset({"admin", "manager", "viewer"})
_RATE_BUCKETS = defaultdict(deque)
_RATE_LOCK = Lock()


def normalized_role(user=None) -> str:
    user = user or current_user
    role = (getattr(user, "role", None) or "viewer").strip().lower()
    return role if role in VALID_ROLES else "viewer"


def require_tenant_access(tenant):
    """Return *tenant* when the signed-in user may access it, otherwise 403."""
    if tenant is None:
        return None
    if not current_user.is_authenticated:
        abort(401, "not authenticated")
    if getattr(current_user, "is_super", False):
        return tenant
    if getattr(current_user, "tenant_id", None) != getattr(tenant, "id", None):
        abort(403, "access denied")
    return tenant


def role_required(*allowed_roles):
    """Require one of the supplied tenant roles; superusers are always allowed."""
    allowed = {role.strip().lower() for role in allowed_roles}
    unknown = allowed - VALID_ROLES
    if unknown:
        raise ValueError(f"unknown roles: {', '.join(sorted(unknown))}")

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401, "not authenticated")
            if not getattr(current_user, "is_super", False) and normalized_role() not in allowed:
                abort(403, "insufficient permissions")
            return view(*args, **kwargs)

        return wrapped

    return decorator


def rate_limit(limit: int, window_seconds: int, *, key_prefix: str, methods=("POST",)):
    """Small in-process safety limit for authentication and public form endpoints."""
    limited_methods = {method.upper() for method in methods}

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if request.method.upper() not in limited_methods:
                return view(*args, **kwargs)
            client = request.remote_addr or "unknown"
            bucket_key = f"{key_prefix}:{client}"
            now = time.monotonic()
            cutoff = now - window_seconds
            with _RATE_LOCK:
                bucket = _RATE_BUCKETS[bucket_key]
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if len(bucket) >= limit:
                    abort(429, "too many requests; please try again later")
                bucket.append(now)
            return view(*args, **kwargs)

        return wrapped

    return decorator
