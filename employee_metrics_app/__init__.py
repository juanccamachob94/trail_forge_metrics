"""
employee_metrics_app.__init__

This module exposes the application factory.  Creating a factory
function allows the application to be created on demand both for the
Flask development server and the scheduled update script.  The
factory binds the SQLAlchemy database, registers the main blueprint
and ensures the database schema exists.  Do not import this module
in global scope of other modules to avoid circular import issues.
"""

from flask import Flask

from .config import Config
from .models import db


def create_app() -> Flask:
    """Application factory used by the Flask CLI and systemd service.

    The factory pattern makes it trivial to create multiple
    application instances with different configurations.  It also
    allows other modules to import the application in a safe way.

    Returns
    -------
    Flask
        A fully configured Flask application instance.
    """
    app = Flask(__name__, static_folder="static", template_folder="templates")
    # Load configuration from environment variables via Config class.
    app.config.from_object(Config)

    # Initialise database support.
    db.init_app(app)

    # Register blueprints here to keep the application modular.
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    # Create all database tables if they do not exist.  This call is
    # idempotent and will do nothing on subsequent executions.  The
    # app_context is required so SQLAlchemy knows which application
    # configuration to use when executing the DDL.
    with app.app_context():
        db.create_all()

    return app