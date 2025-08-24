"""
employee_metrics_app.models

SQLAlchemy models representing the application state.  There are two
primary entities in this system: employees and metrics.  Each
Employee represents a member of the TrailForge squad whose GitHub
activity is tracked.  A Metric record represents a snapshot of
various contribution counts at a specific point in time for a single
employee.  Snapshots enable the application to chart how metrics
change over time and to compute group statistics for the entire team.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

# Create a database instance for the entire application.  It will be
# initialised by the application factory in __init__.py when the
# Flask app is created.
db = SQLAlchemy()


class Employee(db.Model):
    """Model representing an employee in the TrailForge squad.

    Attributes
    ----------
    id : int
        Primary key for the employee.
    name : str
        Display name of the employee.
    github_username : str
        GitHub login used to query the GitHub API.  This value must
        be unique so that metrics are associated with the correct
        individual.
    active : bool
        Indicates whether the employee is currently active at the
        company.  Only active employees will have their metrics
        updated.  Historical data for inactive employees remains in
        the database.
    metrics : list[Metric]
        Back-reference to the metrics captured for this employee.
    """

    __tablename__ = 'employee'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    github_username = db.Column(db.String(128), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationship to metrics.  `lazy=True` creates a dynamic list-like
    # relationship that is loaded on access.  Cascade deletion ensures
    # that when an employee is deleted all of their associated
    # metrics are also removed to maintain referential integrity.
    metrics = db.relationship(
        'Metric', backref='employee', cascade='all, delete-orphan', lazy=True
    )

    def __repr__(self) -> str:
        return f"<Employee id={self.id} name={self.name} username={self.github_username} active={self.active}>"


class Metric(db.Model):
    """Model representing a snapshot of GitHub metrics for an employee.

    Each Metric instance holds the cumulative counts of various GitHub
    activities at the moment the record was created.  The timestamp
    field records when the snapshot was taken.  Storing cumulative
    values allows easy calculation of deltas between two snapshots
    outside of the database if you need to compute weekly changes.

    Attributes
    ----------
    id : int
        Primary key for the metric record.
    employee_id : int
        Foreign key referencing the employee this metric belongs to.
    timestamp : datetime
        Time at which the snapshot was taken.  Defaults to UTC now.
    commits : int
        Number of commits authored by the employee in the target
        repository across the lifetime of the repository.
    prs_opened : int
        Count of pull requests created by the employee in the target
        repository.
    prs_merged : int
        Count of pull requests created by the employee that were merged.
    reviews : int
        Count of pull requests where the employee submitted at least one review.
    """

    __tablename__ = 'metric'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    # timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    timestamp = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    commits = db.Column(db.Integer, default=0)
    prs_opened = db.Column(db.Integer, default=0)
    prs_merged = db.Column(db.Integer, default=0)
    reviews = db.Column(db.Integer, default=0)

    def __repr__(self) -> str:
        return (
            f"<Metric employee_id={self.employee_id} timestamp={self.timestamp.isoformat()} "
            f"commits={self.commits} prs_opened={self.prs_opened} prs_merged={self.prs_merged} "
            f"reviews={self.reviews}>"
        )