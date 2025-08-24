"""
employee_metrics_app.update_metrics

Entry point for the weekly snapshot update.  This module is used by
systemd to run the metrics update on a schedule via the
`employee_metrics_update.service` service.  It can also be invoked
manually with `python -m employee_metrics_app.update_metrics` to
update the database outside of the web interface.

The script creates a Flask application context so that SQLAlchemy can
access the configured database.  It then invokes the update routine
and prints a summary of the records created.  Any logging
configuration should be set up here as desired.
"""

from __future__ import annotations

import logging

from . import create_app
from .github_api import update_metrics_for_all_employees


def main() -> None:
    """Perform an update of all active employee metrics.

    This function initialises the Flask application in the same way as
    the web server, but only for the purpose of performing the update.
    A dedicated application context is created to allow database
    operations.  Logging output is configured to display information
    messages on the console.
    """
    # Configure basic logging.  When run under systemd journal
    # messages are captured automatically.
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
    app = create_app()
    with app.app_context():
        records = update_metrics_for_all_employees()
        print(f"Updated metrics for {len(records)} employee(s).")


if __name__ == '__main__':  # pragma: no cover
    main()