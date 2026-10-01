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

    # step 2.2: init the database here
    # step 2.3: register blueprints here

    return app