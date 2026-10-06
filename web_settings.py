"""Self-service website account settings. All writes target the signed-in user."""
import hmac
import re
import secrets
from functools import wraps

from flask import Blueprint, abort, jsonify, request, session
from flask_login import current_user, login_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from authz import rate_limit
from db import SessionLocal
from models import User, UserSettings, PasswordResetToken

settings_api = Blueprint("settings_api", __name__, url_prefix="/api/settings")
DEFAULTS = {
    "theme": "light",
    "email_new_applicant": False, "email_daily_summary": False,
    "email_weekly_report": False, "email_expiring_job": False,
    "email_flagged_candidate": False, "email_product_news": False,
    "site_alerts": True, "site_sound": False, "site_desktop": False, "site_badge": True,
}


def csrf_token():
    if "settings_csrf" not in session:
        session["settings_csrf"] = secrets.token_urlsafe(32)
    return session["settings_csrf"]


def snapshot(user, db):
    saved = db.get(UserSettings, user.id)
    preferences = dict(DEFAULTS)
    for key, value in (saved.preferences if saved else {}).items():
        if key in DEFAULTS:
            preferences[key] = value
    return {
        "profile": {"full_name": user.full_name or "", "email": user.username,
                    "work_address": saved.work_address if saved else ""},
        "preferences": preferences,
    }


@settings_api.app_context_processor
def inject_settings():
    if not current_user.is_authenticated:
        return {"dashboard_settings": {"preferences": DEFAULTS, "profile": {}}}
    db = SessionLocal()
    try:
        data = snapshot(current_user, db)
        data.update(csrf_token=csrf_token(), user_id=current_user.id)
        return {"dashboard_settings": data}
    finally:
        db.close()


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401, "Your session expired. Please sign in again.")
        if request.method != "GET":
            token = request.headers.get("X-CSRF-Token", "")
            expected = session.get("settings_csrf", "")
            if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
                abort(403, "Please reload this page and try again.")
        return view(*args, **kwargs)
    return wrapped


@settings_api.errorhandler(HTTPException)
def settings_error(error):
    return jsonify(error=error.description), error.code


def payload(allowed):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data or set(data) - set(allowed):
        abort(400, "Invalid settings request.")
    return data


def text_value(value, label, maximum, required=False):
    if not isinstance(value, str):
        abort(400, f"{label} must be text.")
    value = value.strip()
    if len(value) > maximum or (required and not value):
        abort(400, f"{label} must contain {'1' if required else '0'}–{maximum} characters.")
    return value


def verify_password(user, value):
    if not isinstance(value, str) or not value or len(value) > 1024 or not user.check_pw(value):
        abort(400, "Current password is incorrect.")


def saved_settings(db, user_id):
    saved = db.query(UserSettings).filter_by(user_id=user_id).with_for_update().first()
    if saved is None:
        saved = UserSettings(user_id=user_id, work_address="", preferences={})
        db.add(saved)
    return saved


@settings_api.get("")
@authenticated
def get_settings():
    db = SessionLocal()
    try:
        return jsonify(**snapshot(current_user, db), csrf_token=csrf_token())
    finally:
        db.close()


@settings_api.patch("/profile")
@authenticated
@rate_limit(30, 300, key_prefix="web-settings-profile", methods=("PATCH",))
def update_profile():
    data = payload({"field", "value", "current_password"})
    field = data.get("field")
    if not isinstance(field, str) or field not in {"full_name", "email", "work_address"}:
        abort(400, "Choose a valid profile field.")
    value = text_value(data.get("value"), "Value", {"full_name": 200, "email": 320, "work_address": 1000}[field], field != "work_address")
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        if field == "email":
            verify_password(user, data.get("current_password"))
            value = value.lower()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                abort(400, "Enter a valid email address.")
            if db.query(User).filter(func.lower(User.username) == value, User.id != user.id).first():
                abort(409, "That email address is already in use.")
            user.username = value
            db.query(PasswordResetToken).filter_by(user_id=user.id, used=False).update({"used": True})
        elif field == "full_name":
            user.full_name = value
        else:
            saved_settings(db, user.id).work_address = value
        db.commit()
        return jsonify(**snapshot(user, db), message="Profile updated.")
    except IntegrityError:
        db.rollback()
        abort(409, "These details could not be saved. Reload and try again.")
    finally:
        db.close()


@settings_api.post("/password")
@authenticated
@rate_limit(10, 300, key_prefix="web-settings-password")
def update_password():
    data = payload({"current_password", "new_password", "confirm_password"})
    new = data.get("new_password")
    if not isinstance(new, str) or not 8 <= len(new) <= 128:
        abort(400, "Use a password between 8 and 128 characters.")
    if new != data.get("confirm_password"):
        abort(400, "New passwords do not match.")
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        verify_password(user, data.get("current_password"))
        if user.check_pw(new):
            abort(400, "Choose a password different from your current password.")
        user.set_pw(new)
        db.query(PasswordResetToken).filter_by(user_id=user.id, used=False).update({"used": True})
        db.commit()
        # Password-bound login IDs invalidate every old session. Refresh this one.
        session["_remember"] = "clear"
        login_user(user, remember=False, fresh=True)
        return jsonify(message="Password changed. Other sessions have been signed out.")
    finally:
        db.close()


@settings_api.patch("/preferences")
@authenticated
def update_preferences():
    data = payload(DEFAULTS)
    for key, value in data.items():
        if key == "theme":
            if value not in ("light", "dark"):
                abort(400, "Choose Light or Dark.")
        elif type(value) is not bool:
            abort(400, "Notification preferences must be on or off.")
    db = SessionLocal()
    try:
        saved = saved_settings(db, current_user.id)
        saved.preferences = {**saved.preferences, **data}
        db.commit()
        return jsonify(**snapshot(current_user, db), message="Preferences saved.")
    except IntegrityError:
        db.rollback()
        abort(409, "Settings changed in another window. Reload and try again.")
    finally:
        db.close()
