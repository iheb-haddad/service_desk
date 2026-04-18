from pathlib import Path

from flask import Flask, request

from app.config import BASE_DIR, Config
from app.extensions import csrf, db, login_manager
from app.models import User


def create_app(config_class: type = Config) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_object(config_class)

    upload_dir = Path(app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    @app.before_request
    def _escalation_tick():
        if not request.endpoint or request.endpoint.startswith("static"):
            return
        from app.services.escalation import process_escalations

        try:
            process_escalations()
        except Exception:
            app.logger.exception("Escalade automatique impossible")

    from app.routes import admin, agent, attachments, auth, employe, main, notifications

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(employe.bp)
    app.register_blueprint(agent.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(notifications.bp)
    app.register_blueprint(attachments.bp)

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from sqlalchemy import func

        from app.models import Notification

        def notif_count():
            if not current_user.is_authenticated:
                return 0
            return Notification.query.filter_by(
                destinataire_id=current_user.id, lue=False
            ).count()

        def notif_cursor_id():
            if not current_user.is_authenticated:
                return 0
            mid = (
                db.session.query(func.max(Notification.id))
                .filter(Notification.destinataire_id == current_user.id)
                .scalar()
            )
            return int(mid or 0)

        return {
            "notif_count": notif_count,
            "notif_cursor_id": notif_cursor_id(),
        }

    return app
