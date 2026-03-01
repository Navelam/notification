"""Route registration helpers."""

from routes.notification_routes import notification_bp


def register_blueprints(app):
    """Register blueprints exposed by this package."""

    app.register_blueprint(notification_bp)
