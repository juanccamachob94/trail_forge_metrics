"""
employee_metrics_app.github_api

Helper functions to interact with the GitHub REST API.  This module
defines a set of functions to collect contribution statistics for
GitHub users in a specific repository.  It relies only on the
standard `requests` library and therefore avoids bringing in the
graph-QL client.  The functions are written defensively: failures to
communicate with GitHub or unexpected responses result in zeroed
metrics rather than raising exceptions so that a single failing API
call does not abort the entire update process.

The GitHub API has a rate limit for authenticated requests (currently
5,000 requests per hour).  Updating metrics for a handful of
employees once per week should comfortably sit within this limit.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

import requests

from .config import Config
from .models import Employee, Metric, db


logger = logging.getLogger(__name__)

# Base URL for the GitHub REST API.  Using api.github.com ensures
# HTTPS.  All endpoints are versioned implicitly according to the
# Accept header.
API_BASE = "https://api.github.com"


def _request(url: str, params: Optional[Dict[str, str]] = None) -> Optional[requests.Response]:
    """Issue an authenticated GET request to GitHub.

    Parameters
    ----------
    url : str
        Full URL to request.
    params : dict[str, str], optional
        Optional query parameters for the request.

    Returns
    -------
    requests.Response | None
        Response object on success or None on failure.
    """
    token = Config.GITHUB_TOKEN
    if not token:
        logger.warning("GITHUB_TOKEN is not set; cannot query GitHub API.")
        return None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {token}",
        "User-Agent": "TrailForge-Metrics-App"
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        # GitHub may return a 202 status for some endpoints when data is
        # being computed.  In that case we attempt to poll a few times
        # before giving up.  See docs for `/stats/*` endpoints.
        retries = 0
        while resp.status_code == 202 and retries < 5:
            time.sleep(2 ** retries)  # exponential backoff
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            retries += 1
        if resp.status_code >= 400:
            logger.warning(
                "GitHub API request to %s failed with status %s: %s",
                url, resp.status_code, resp.text
            )
            return None
        return resp
    except requests.RequestException as exc:
        logger.error("Error while requesting %s: %s", url, exc)
        return None

def fetch_contributor_stats(owner: str, repo: str) -> List[dict]:
    """Retrieve contributor statistics for a repository.

    This endpoint returns weekly commit, addition and deletion counts
    for each contributor.  If the repository is very large GitHub may
    return a 202 status code, in which case the caller should retry
    after a short delay.  See _request for retry logic.

    Parameters
    ----------
    owner : str
        Owner of the repository.
    repo : str
        Name of the repository.

    Returns
    -------
    list[dict]
        List of contributor statistics, possibly empty.
    """
    url = f"{API_BASE}/repos/{owner}/{repo}/stats/contributors"
    resp = _request(url)
    if not resp:
        return []
    try:
        return resp.json()
    except ValueError:
        logger.error("Failed to decode JSON from contributor stats response for %s/%s", owner, repo)
        return []


def _aggregate_contributor_totals(stats: List[dict]) -> Dict[str, Dict[str, int]]:
    """Aggregate weekly statistics into total counts for each contributor.

    Parameters
    ----------
    stats : list[dict]
        Raw response from the `/stats/contributors` endpoint.

    Returns
    -------
    dict[str, dict[str, int]]
        Mapping of contributor login to a dictionary of totals with
        key `commits`.
    """
    totals: Dict[str, Dict[str, int]] = {}
    for contributor in stats:
        author = contributor.get('author') or {}
        login = author.get('login')
        if not login:
            continue
        weeks = contributor.get('weeks', [])
        commits_sum = sum(week.get('c', 0) for week in weeks)
        totals[login] = {
            'commits': commits_sum,
        }
    return totals


def _search_total_count(owner: str, repo: str, terms: list[str]) -> int:
    # arma 'q' con espacios; requests har� el encoding correcto
    query = " ".join(terms + [f"repo:{owner}/{repo}"])
    url = f"{API_BASE}/search/issues"
    resp = _request(url, params={'q': query})
    if not resp:
        return 0
    try:
        return int(resp.json().get('total_count', 0))
    except ValueError:
        logger.error("Failed to decode JSON from search for %s/%s: %s", owner, repo, terms)
        return 0


def fetch_prs_opened(owner: str, repo: str, username: str) -> int:
    return _search_total_count(owner, repo, ["is:pr", f"author:{username}"])


def fetch_prs_merged(owner: str, repo: str, username: str) -> int:
    return _search_total_count(owner, repo, ["is:pr", f"author:{username}", "is:merged"])


def fetch_reviews(owner: str, repo: str, username: str) -> int:
    return _search_total_count(owner, repo, ["is:pr", f"reviewed-by:{username}"])


def update_metrics_for_employee(employee: Employee) -> Metric | None:
    """Update metrics for a single employee.

    For the provided employee this function queries GitHub for
    cumulative commit counts, as well as the total number of pull
    requests opened, pull requests merged, and reviews submitted in
    the target repository.  A new Metric record is persisted in the
    database to capture the current snapshot.  Errors contacting
    GitHub result in a partial update or zero values; however a Metric
    record will always be created to record the attempt.

    Parameters
    ----------
    employee : Employee
        Employee whose metrics are being updated.

    Returns
    -------
    Metric | None
        The newly created Metric record or None if the update could
        not be performed due to missing configuration.
    """
    owner = Config.REPO_OWNER
    repo = Config.REPO_NAME
    if not (owner and repo and Config.GITHUB_TOKEN):
        logger.warning(
            "Cannot update metrics because one of REPO_OWNER, REPO_NAME or GITHUB_TOKEN is unset."
        )
        return None

    # Fetch and aggregate commit statistics for the entire repository.
    stats = fetch_contributor_stats(owner, repo)
    totals_map = _aggregate_contributor_totals(stats)
    totals = totals_map.get(employee.github_username, {'commits': 0})

    # Fetch PRs opened, PRs merged, and reviews by this user in the repository.
    prs_opened = fetch_prs_opened(owner, repo, employee.github_username)
    prs_merged = fetch_prs_merged(owner, repo, employee.github_username)
    reviews = fetch_reviews(owner, repo, employee.github_username)

    metric = Metric(
        employee_id=employee.id,
        commits=totals.get('commits', 0),
        prs_opened=prs_opened,
        prs_merged=prs_merged,
        reviews=reviews,
    )
    db.session.add(metric)
    db.session.commit()
    logger.info(
        "Recorded metrics for %s: commits=%s, prs_opened=%s, prs_merged=%s, reviews=%s",
        employee.github_username,
        metric.commits,
        metric.prs_opened,
        metric.prs_merged,
        metric.reviews,
    )
    return metric


def update_metrics_for_all_employees() -> List[Metric]:
    """Update metrics for all active employees.

    Retrieves all employees marked as active in the database and
    sequentially calls `update_metrics_for_employee` on each one.  A
    list of Metric objects, one per employee, is returned.  If
    configuration values are missing the list may be empty.

    Returns
    -------
    list[Metric]
        List of newly created metric records.
    """
    employees: List[Employee] = Employee.query.filter_by(active=True).all()
    new_records: List[Metric] = []
    for emp in employees:
        record = update_metrics_for_employee(emp)
        if record is not None:
            new_records.append(record)
    return new_records