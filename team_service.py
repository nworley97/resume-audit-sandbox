"""Shared team creation for website settings and the native app."""
import re
import secrets

from flask import abort
from sqlalchemy import func

from models import Tenant, User
from subscription_models import check_can_add_seat


def member_dict(user):
    name = user.full_name or user.username
    return {"id": user.id, "name": name, "email": user.username,
            "role": user.role or "viewer",
            "initials": "".join(word[0] for word in name.split()[:2]).upper() or "U"}


def create_member(db, tenant_id, data):
    if not isinstance(data, dict) or set(data) - {"name", "email", "role"}:
        abort(400, "Invalid team member request.")
    values = {}
    for key, limit in (("name", 200), ("email", 320), ("role", 20)):
        value = data.get(key, "manager" if key == "role" else "")
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
            abort(400, f"{key.title()} must contain 1–{limit} characters.")
        values[key] = value.strip()
    values["email"] = values["email"].lower()
    values["role"] = values["role"].lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]):
        abort(400, "Enter a valid email address.")
    if values["role"] not in {"admin", "manager", "viewer"}:
        abort(400, "Role must be admin, manager, or viewer.")
    # Serialize seat checks and inserts for this tenant on PostgreSQL.
    if not db.query(Tenant).filter_by(id=tenant_id).with_for_update().first():
        abort(404)
    can_add, used, limit = check_can_add_seat(tenant_id, db)
    if not can_add:
        abort(409, f"Seat limit reached ({used}/{limit}). Add a seat or upgrade your plan in billing.")
    if db.query(User).filter(func.lower(User.username) == values["email"]).first():
        abort(409, "A user with this email already exists.")
    password = secrets.token_urlsafe(18)
    user = User(username=values["email"], full_name=values["name"],
                role=values["role"], tenant_id=tenant_id)
    user.set_pw(password)
    db.add(user)
    db.flush()
    return {**member_dict(user), "temp_password": password}


def protect_last_admin(db, member):
    if member.role == "admin" and not db.query(User).filter(
        User.tenant_id == member.tenant_id, User.role == "admin", User.id != member.id
    ).first():
        abort(409, "Keep at least one admin on your team.")
