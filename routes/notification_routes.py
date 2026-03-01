"""Notification module routes.

Blueprint features:
- create notifications with role-based permissions
- fetch dropdown summary (latest 5 + unread count)
- list page and detail page
- mark individual/all notifications as read
"""

from datetime import datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, or_

from extensions import db
from model import User
from models.notification import Notification, NotificationRead


notification_bp = Blueprint("notifications", __name__)


ROLE_CHOICES = {
    "all": "All",
    "public": "Public",
    "principal": "Principal",
    "hod": "HOD",
    "coordinator": "Coordinator",
    "teacher": "Teacher",
    "student": "Student",
}


def _normalize_role(value: str | None) -> str:
    return (value or "").strip().lower()


def _user_department(user) -> str | None:
    return (getattr(user, "department", None) or None)


def _can_create_notification(user, target_role: str, department: str | None) -> tuple[bool, str]:
    role = _normalize_role(getattr(user, "role", ""))

    if role == "principal":
        if target_role not in ROLE_CHOICES:
            return False, "Invalid target role"
        return True, ""

    if role == "coordinator":
        if target_role not in ROLE_CHOICES:
            return False, "Invalid target role"
        return True, ""

    if role == "hod":
        if department != _user_department(user):
            return False, "HOD can notify only their own department"
        return True, ""

    return False, "You are not allowed to create notifications"


def _visible_notifications_query(user):
    """Builds visibility query from the rules in the task."""

    role = _normalize_role(getattr(user, "role", ""))
    user_department = _user_department(user)

    return Notification.query.filter(
        Notification.is_active.is_(True),
        or_(
            Notification.target_role == "all",
            Notification.target_role == "public",
            Notification.target_role == role,
            and_(
                Notification.department.isnot(None),
                Notification.department == user_department,
            ),
        ),
    )


def _serialize_notification(n: Notification, include_full: bool = False):
    payload = {
        "id": n.id,
        "title": n.title,
        "message_preview": n.preview(90),
        "target_role": n.target_role,
        "department": n.department,
        "created_at": n.created_at.strftime("%d %b %Y, %I:%M %p"),
        "detail_url": url_for("notifications.notification_detail", notification_id=n.id),
    }
    if include_full:
        payload["message"] = n.message
    return payload


@notification_bp.route("/notifications/create", methods=["GET", "POST"])
@login_required
def create_notification():
    """Create notification form (Principal, Coordinator, HOD)."""

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        target_role = _normalize_role(request.form.get("target_role")) or "all"
        requested_department = (request.form.get("department") or "").strip() or None

        if not title or not message:
            flash("Title and message are required.", "danger")
            return redirect(url_for("notifications.create_notification"))

        # HOD is always restricted to their department regardless of form input.
        creator_role = _normalize_role(getattr(current_user, "role", ""))
        department = requested_department
        if creator_role == "hod":
            department = _user_department(current_user)
            target_role = "all"

        allowed, error = _can_create_notification(current_user, target_role, department)
        if not allowed:
            flash(error, "danger")
            return redirect(url_for("notifications.create_notification"))

        notification = Notification(
            title=title,
            message=message,
            created_by=current_user.id,
            target_role=target_role,
            department=department,
            is_active=True,
        )
        db.session.add(notification)
        db.session.commit()
        flash("Notification created successfully.", "success")
        return redirect(url_for("notifications.notifications_page"))

    return render_template(
        "notifications.html",
        notifications=[],
        role_choices=ROLE_CHOICES,
        now=datetime.now(),
        show_create_form=True,
    )


@notification_bp.route("/notifications")
@login_required
def notifications_page():
    notifications = _visible_notifications_query(current_user).order_by(Notification.created_at.desc()).all()
    return render_template(
        "notifications.html",
        notifications=notifications,
        role_choices=ROLE_CHOICES,
        show_create_form=False,
        now=datetime.now(),
    )


@notification_bp.route("/notification/<int:notification_id>")
@login_required
def notification_detail(notification_id: int):
    notification = _visible_notifications_query(current_user).filter(Notification.id == notification_id).first()
    if not notification:
        abort(404)

    read_entry = NotificationRead.query.filter_by(
        notification_id=notification.id,
        user_id=current_user.id,
    ).first()
    if not read_entry:
        db.session.add(NotificationRead(notification_id=notification.id, user_id=current_user.id))
        db.session.commit()

    return render_template("notification_detail.html", notification=notification, now=datetime.now())


@notification_bp.route("/notifications/api/summary")
@login_required
def notifications_summary_api():
    query = _visible_notifications_query(current_user)
    latest_five = query.order_by(Notification.created_at.desc()).limit(5).all()

    read_subquery = db.session.query(NotificationRead.notification_id).filter(
        NotificationRead.user_id == current_user.id
    )
    unread_count = query.filter(~Notification.id.in_(read_subquery)).count()

    return jsonify(
        {
            "success": True,
            "unread_count": unread_count,
            "notifications": [_serialize_notification(n) for n in latest_five],
        }
    )


@notification_bp.route("/notifications/api/read/<int:notification_id>", methods=["POST"])
@login_required
def mark_notification_read(notification_id: int):
    notification = _visible_notifications_query(current_user).filter(Notification.id == notification_id).first()
    if not notification:
        return jsonify({"success": False, "message": "Notification not found"}), 404

    exists = NotificationRead.query.filter_by(notification_id=notification.id, user_id=current_user.id).first()
    if not exists:
        db.session.add(NotificationRead(notification_id=notification.id, user_id=current_user.id))
        db.session.commit()

    return jsonify({"success": True})


@notification_bp.route("/notifications/api/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    notifications = _visible_notifications_query(current_user).all()
    visible_ids = {n.id for n in notifications}

    if visible_ids:
        existing = {
            row.notification_id
            for row in NotificationRead.query.filter(
                NotificationRead.user_id == current_user.id,
                NotificationRead.notification_id.in_(visible_ids),
            ).all()
        }

        for notification_id in visible_ids - existing:
            db.session.add(NotificationRead(notification_id=notification_id, user_id=current_user.id))

        db.session.commit()

    return jsonify({"success": True})


@notification_bp.app_context_processor
def inject_notification_template_data():
    """Global data used by the bell icon and dropdown templates."""

    if not current_user.is_authenticated:
        return {
            "notification_unread_count": 0,
            "notification_latest": [],
        }

    query = _visible_notifications_query(current_user)
    latest = query.order_by(Notification.created_at.desc()).limit(5).all()

    read_subquery = db.session.query(NotificationRead.notification_id).filter(
        NotificationRead.user_id == current_user.id
    )
    unread_count = query.filter(~Notification.id.in_(read_subquery)).count()

    return {
        "notification_unread_count": unread_count,
        "notification_latest": latest,
    }
