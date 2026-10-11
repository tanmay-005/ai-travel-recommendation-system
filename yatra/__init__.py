"""Yatra-Go: builds the Flask app."""
from flask import Flask, session

from yatra.config import BASE_DIR, Config


def create_app(config=None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    from yatra.db import init_db
    with app.app_context():
        init_db()
        
    from yatra.routes import auth, geocode, pages, places, saved
    app.register_blueprint(pages.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(places.bp)
    app.register_blueprint(saved.bp)
    app.register_blueprint(geocode.bp)
    
    @app.context_processor
    def inject_user():
        """Every template can use {{ current_user }}: None, or {"id": .., "username": ..}."""
        uid = session.get("user_id")
        return {"current_user": {"id": uid, "username": session.get("username")} if uid else None}
    return app