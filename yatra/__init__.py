"""Yatra-Go: builds the Flask app."""
from flask import Flask

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

    return app