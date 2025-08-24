# Employee Metrics Application

This repository contains a small Flask application for monitoring the
GitHub activity of a development squad.  Each employee is associated
with a GitHub username and the application records their cumulative
contribution statistics on a periodic basis.  A group dashboard
provides a summary of the entire team and individual dashboards
visualise the historical metrics for each member.

## Features

- Register, update and remove employees stored in a local SQLite database.
- Pull commit, addition, deletion, pull request and issue counts from the
  GitHub API for each active employee.
- Automatically snapshot metrics once per week via systemd or trigger an
  update manually through the web interface.
- Display aggregated statistics and trends for the entire team as well
  as per‑employee dashboards with interactive line charts powered by
  Chart.js.
- Simple, modern UI using the TrailForge colour palette and the
  provided squad logo.

## Installation

The application is designed to run on a Raspberry Pi running
Raspbian with Python 3.11.  The following steps assume you are
logged in as the `developer` user and that the project resides in
`/home/developer/Documents/employee_metrics_app`.

1. **Clone the repository** (or copy the provided source code into
   place):

   ```sh
   cd ~/Documents
   git clone https://github.com/perfectsense/tv-azteca employee_metrics_app
   cd employee_metrics_app
   ```

   If you have been provided with a zip archive of the application
   instead of cloning from GitHub, extract it into
   `~/Documents/employee_metrics_app` and change into that directory.

2. **Create a Python virtual environment and install dependencies**:

   ```sh
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

   The virtual environment isolates the application's dependencies
   from the system Python installation.  Activating it ensures that
   the `flask` command and all Python modules resolve correctly.

3. **Provide configuration in a `.env` file** (or via systemd).
   Copy the provided `.env.example` to `.env` and edit the values:

   ```sh
   cp .env.example .env
   nano .env
   ```

   At a minimum you must set `GITHUB_TOKEN`, `REPO_OWNER` and
   `REPO_NAME`.  The GitHub token must have permission to read
   statistics from the repository you want to analyse.  The
   `SECRET_KEY` should be replaced with a long random string for
   session security.

4. **Initialise the database**.  The application uses SQLite and
   will create the database file automatically on first run.  To
   initialise the schema manually you can run a tiny helper script:

   ```sh
   python -c "from employee_metrics_app import create_app; app = create_app(); print('Database initialised.')"
   ```

   Running any route for the first time will also create the database
   automatically.

5. **Run the application for development**:

   Activate the virtual environment if it is not already active and
   launch the Flask development server on all interfaces:

   ```sh
   export FLASK_APP=employee_metrics_app.app
   flask run --host=0.0.0.0 --port=5000
   ```

   You can now open a browser on any device within your LAN and
   navigate to `http://<raspberry-pi-ip>:5000/` to access the
   dashboard.

## Deployment with systemd

Systemd unit files have been provided to run the web server and
automatically update the metrics each week.  Copy the following
service and timer definitions into `/etc/systemd/system/` and adjust
paths if necessary (they are included in the assignment description):

- `employee_metrics.service` – runs the Flask web server on boot.
- `employee_metrics_update.service` – executes the metric update script.
- `employee_metrics_update.timer` – schedules the update service for
  every Friday at 09:00.

After copying the unit files you can enable and start the services:

```sh
sudo systemctl daemon-reload
sudo systemctl enable employee_metrics.service employee_metrics_update.timer
sudo systemctl start employee_metrics.service employee_metrics_update.timer
```

The web server runs under the `developer` user inside the virtual
environment located at `~/Documents/employee_metrics_app/venv`.  The
update service imports the application and runs
`employee_metrics_app.update_metrics` as defined in the unit file.

## Manual updates

While the timer will execute weekly snapshots automatically you can
trigger an update at any time from within the web application.  Visit
the team dashboard and click “Update Metrics”.  You will be asked
for confirmation before the update begins.

## Security considerations

- **GitHub token** – Store your personal access token securely.  The
  `.env` file should never be committed to version control.  When
  running under systemd the token can be specified via the
  `Environment` directive to avoid storing secrets on disk.
- **HTTPS** – For deployment in a production environment exposed to the
  internet you should place the Flask application behind a reverse
  proxy such as Nginx and terminate TLS there.  This sample setup
  assumes a trusted local network.
- **Access control** – This demonstration application does not
  implement authentication.  If deployed outside of an internal
  network you should add a login system to restrict access to the
  dashboards and administrative functions.