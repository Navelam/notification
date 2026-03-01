"""Notification domain models.

This module is intentionally self-contained so it can be imported by existing
Flask apps that already expose an ``extensions.db`` SQLAlchemy instance and a
``User`` model in ``model.py``.
"""

from datetime import datetime

from extensions import db


class Notification(db.Model):
    """Role and/or department scoped notification."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    target_role = db.Column(
        db.Enum(
            "all",
            "public",
            "principal",
            "hod",
            "coordinator",
            "teacher",
            "student",
            name="notification_target_role",
            native_enum=False,
        ),
        nullable=False,
        default="all",
        index=True,
    )
    # Set only for department-scoped notifications (e.g., HOD specific).
    department = db.Column(db.String(120), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    creator = db.relationship("User", backref=db.backref("created_notifications", lazy="dynamic"))

    def preview(self, length: int = 120) -> str:
        """Small helper for dropdown snippets."""
        if len(self.message) <= length:
            return self.message
        return f"{self.message[:length - 3]}..."


class NotificationRead(db.Model):
    """Tracks per-user read state to support unread count and badge rendering."""

    __tablename__ = "notification_reads"

    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(
        db.Integer,
        db.ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("notification_id", "user_id", name="uq_notification_user_read"),
    )

    notification = db.relationship("Notification", backref=db.backref("read_receipts", lazy="dynamic"))
