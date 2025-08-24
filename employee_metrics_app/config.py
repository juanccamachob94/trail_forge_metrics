"""
employee_metrics_app.config

Centralised configuration for the employee metrics application.  All
configuration values are loaded from the environment, optionally
falling back to sensible defaults.  The environment variables are
loaded from a .env file if present using python‑dotenv.  See
`.env.example` for a template of required variables.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Determine base directory of the package to construct default paths.
BASE_DIR = Path(__file__).resolve().parent

# Attempt to load a .env file one directory up from this module.  If
# the file does not exist then load_dotenv silently ignores it.  The
# systemd service may also inject environment variables directly,
# meaning a .env file is optional when running under systemd.
env_path = BASE_DIR.parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)


class Config:
    """Default configuration values for the Flask application.

    Attributes are loaded lazily from the environment when
    `Config` is imported.  Environment variables override defaults
    defined here.  See the README for descriptions of each option.
    """

    # Secret key used by Flask to sign session cookies and CSRF tokens.
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me-please")

    # Database connection URI.  Default uses a local SQLite file in
    # the package directory.  When deploying to other environments you
    # can set DATABASE_URL to point at a different database if
    # required.
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'employee_metrics.db').as_posix()}"
    )

    # Disables SQLAlchemy's event system which consumes additional
    # resources.  It is only needed when you require the object
    # modification events.  Leaving it off is recommended.
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # GitHub personal access token used to authenticate API requests.
    # This should be a token with at least `repo` scope if the
    # repository is private.  The token may be defined in the .env
    # file or injected via systemd's Environment directive.
    GITHUB_TOKEN: str | None = os.environ.get("GITHUB_TOKEN")

    # Owner of the GitHub repository to analyse.  Required for the
    # update script to know which repository to gather metrics from.
    REPO_OWNER: str | None = os.environ.get("REPO_OWNER")

    # Name of the GitHub repository to analyse.  Required for the
    # update script to know which repository to gather metrics from.
    REPO_NAME: str | None = os.environ.get("REPO_NAME")