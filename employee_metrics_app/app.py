"""
employee_metrics_app.app

This module exposes a top‑level Flask application instance for use
with the Flask CLI and external WSGI servers.  Importing the
`app` object will automatically create the application using the
factory in `employee_metrics_app.__init__`.  The `__main__` block
provides a convenient entry point for running the server locally.
"""

from . import create_app

# Create the application instance at module import time.  Flask's
# built‑in development server and the systemd unit rely on this
# variable being present.
app = create_app()


def main() -> None:
    """Run the development server if executed directly.

    This function simply wraps `app.run()` so that the module can be
    executed with `python -m employee_metrics_app.app`.  The server
    binds to all network interfaces so that it is reachable from other
    devices on the LAN.
    """
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":  # pragma: no cover
    main()