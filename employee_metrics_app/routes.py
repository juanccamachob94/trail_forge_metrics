"""
employee_metrics_app.routes

This module defines the HTTP routes for the web application using a
Flask Blueprint.  The views are responsible for rendering pages,
handling form submissions and coordinating with the GitHub API.  All
database access occurs within the context of these view functions.
"""

from __future__ import annotations

import json
from datetime import timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .models import db, Employee, Metric
from .github_api import update_metrics_for_all_employees

LOCAL_TZ = ZoneInfo("America/Mexico_City")

def to_local(dt):
    """Convierte un datetime (naive=asumido UTC) a America/Mexico_City."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ)


# Define the main blueprint.  All routes are anchored at the root
# URL because this is the only application in the project.
bp = Blueprint('main', __name__)


def _latest_metric(employee: Employee) -> Optional[Metric]:
    """Return the most recent metric for an employee or None.

    Parameters
    ----------
    employee : Employee
        Employee whose latest metric is requested.

    Returns
    -------
    Metric | None
        The newest Metric instance or None if no metrics exist.
    """
    return (
        Metric.query.filter_by(employee_id=employee.id)
        .order_by(Metric.timestamp.desc())
        .first()
    )


def _aggregate_group_metrics() -> Tuple[Dict[str, int], Dict[str, List[Any]]]:
    """Compute aggregated metrics and time series for the whole team.

    Aggregated metrics are based on the most recent snapshot for each
    employee.  The time series is built by summing metrics across
    all employees for each snapshot date.  This data is used by the
    index page to render summary cards and charts.

    Returns
    -------
    tuple
        A tuple of (summary, chart_data) where summary is a
        dictionary of the latest total counts and chart_data is
        structured for Chart.js consumption.
    """
    employees = Employee.query.all()
    summary = {
        'commits': 0,
        'prs_opened': 0,
        'prs_merged': 0,
        'reviews': 0,
    }
    # Compute totals from latest metrics per employee
    for emp in employees:
        latest = _latest_metric(emp)
        if not latest:
            continue
        summary['commits'] += latest.commits
        summary['prs_opened'] += latest.prs_opened
        summary['prs_merged'] += latest.prs_merged
        summary['reviews'] += latest.reviews

    # Build time series by date across all metrics records
    series: Dict[str, Dict[str, int]] = {}
    metrics = Metric.query.order_by(Metric.timestamp.asc()).all()
    for m in metrics:
        # date_str = m.timestamp.date().isoformat()
        date_str = to_local(m.timestamp).date().isoformat()
        if date_str not in series:
            series[date_str] = {'commits': 0, 'prs_opened': 0, 'prs_merged': 0, 'reviews': 0}
        series[date_str]['commits'] += m.commits
        series[date_str]['prs_opened'] += m.prs_opened
        series[date_str]['prs_merged'] += m.prs_merged
        series[date_str]['reviews'] += m.reviews

    # Sort by date and build lists for Chart.js
    sorted_dates = sorted(series.keys())
    chart_data = {
        'labels': sorted_dates,
        'commits': [series[d]['commits'] for d in sorted_dates],
        'prs_opened': [series[d]['prs_opened'] for d in sorted_dates],
        'prs_merged': [series[d]['prs_merged'] for d in sorted_dates],
        'reviews': [series[d]['reviews'] for d in sorted_dates],
    }
    return summary, chart_data


@bp.app_template_filter("tzdate_iso")
def tzdate_iso(dt):
    """Fecha local (YYYY-MM-DD) en America/Mexico_City."""
    return to_local(dt).date().isoformat()


@bp.route('/')
def index():
    """Render the group dashboard.

    Displays aggregated metrics for the entire team, a line chart
    showing how the metrics have changed over time and a list of
    employees with links to their individual dashboards.  Buttons are
    provided to register a new employee and to manually trigger a
    metrics update.
    """
    employees = Employee.query.order_by(Employee.name.asc()).all()
    group_summary, chart_data = _aggregate_group_metrics()
    # Pass the raw chart_data dictionary to the template.  Jinja's
    # `tojson` filter will serialise it appropriately when embedded
    # into JavaScript.
    return render_template(
        'index.html',
        employees=employees,
        summary=group_summary,
        chart_data=chart_data,
    )


@bp.route('/update', methods=['GET', 'POST'])
def update():
    """Handle manual updates of all metrics.

    On GET a confirmation page is shown to the user.  If the user
    submits the POST request then the update routine is executed and
    the user is redirected back to the index page with a flash
    message.  This two step process avoids accidental execution of
    potentially long running updates.
    """
    if request.method == 'POST':
        # Trigger metrics update.  Running this synchronously will
        # block the request until completion.  For a small team this
        # should not be an issue.  If the team grows large consider
        # offloading this call to a background worker.
        count = len(update_metrics_for_all_employees())
        flash(f"Metrics updated for {count} active employee(s).", category='success')
        return redirect(url_for('main.index'))
    return render_template('update_confirm.html')


@bp.route('/employees/add', methods=['GET', 'POST'])
def add_employee():
    """Add a new employee to the database."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('github_username', '').strip()
        active = bool(request.form.get('active'))
        if not name or not username:
            flash('Name and GitHub username are required.', category='danger')
            return render_template('employee_form.html', employee=None)
        # Ensure the username is unique
        if Employee.query.filter_by(github_username=username).first():
            flash('GitHub username already exists.', category='danger')
            return render_template('employee_form.html', employee=None)
        employee = Employee(name=name, github_username=username, active=active)
        db.session.add(employee)
        db.session.commit()
        flash('Employee registered successfully.', category='success')
        return redirect(url_for('main.index'))
    return render_template('employee_form.html', employee=None)


@bp.route('/employees/<int:employee_id>/edit', methods=['GET', 'POST'])
def edit_employee(employee_id: int):
    """Edit an existing employee."""
    employee = Employee.query.get_or_404(employee_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('github_username', '').strip()
        active = bool(request.form.get('active'))
        if not name or not username:
            flash('Name and GitHub username are required.', category='danger')
            return render_template('employee_form.html', employee=employee)
        # If the username has changed check uniqueness
        if username != employee.github_username and Employee.query.filter_by(github_username=username).first():
            flash('GitHub username already exists.', category='danger')
            return render_template('employee_form.html', employee=employee)
        employee.name = name
        employee.github_username = username
        employee.active = active
        db.session.commit()
        flash('Employee updated successfully.', category='success')
        return redirect(url_for('main.employee_detail', employee_id=employee.id))
    return render_template('employee_form.html', employee=employee)


@bp.route('/employees/<int:employee_id>/delete', methods=['POST'])
def delete_employee(employee_id: int):
    """Delete an employee and all of their metrics."""
    employee = Employee.query.get_or_404(employee_id)
    db.session.delete(employee)
    db.session.commit()
    flash('Employee deleted successfully.', category='success')
    return redirect(url_for('main.index'))


@bp.route('/employees/<int:employee_id>')
def employee_detail(employee_id: int):
    """Render the dashboard for a single employee."""
    employee = Employee.query.get_or_404(employee_id)
    # Latest snapshot for summary
    latest = _latest_metric(employee)
    # Build time series for this employee
    records = (
        Metric.query.filter_by(employee_id=employee.id)
        .order_by(Metric.timestamp.asc())
        .all()
    )
    # labels = [rec.timestamp.date().isoformat() for rec in records]
    labels = [to_local(rec.timestamp).date().isoformat() for rec in records]
    chart_data = {
        'labels': labels,
        'commits': [rec.commits for rec in records],
        'prs_opened': [rec.prs_opened for rec in records],
        'prs_merged': [rec.prs_merged for rec in records],
        'reviews': [rec.reviews for rec in records],
    }
    return render_template(
        'employee_detail.html',
        employee=employee,
        latest=latest,
        chart_data=chart_data,
    )