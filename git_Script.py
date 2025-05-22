#!/usr/bin/env python3
"""
commit_with_date.py — stage and commit work using consecutive dates in 2024.

Usage:
    python commit_with_date.py

It will:
  1. Select the next date from .last_commit_date, starting at 2024-01-01
  2. Ask for a commit message describing what you actually did
  3. git add . / commit with that date / push
  4. Save that date as the new "last date"
"""

import subprocess
import sys
import os
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, ".last_commit_date")
REPO_DIR = SCRIPT_DIR
START_DATE = datetime.fromisoformat("2025-01-01T00:00:00")
END_DATE = datetime.fromisoformat("2025-12-31T00:00:00")


def get_git_identity():
    """Return the configured Git name and email for this or a nested repo."""
    identity = {}
    for key in ("user.name", "user.email"):
        result = subprocess.run(
            ["git", "config", "--get", key],
            capture_output=True,
            text=True,
            cwd=REPO_DIR,
        )
        if result.returncode == 0 and result.stdout.strip():
            identity[key] = result.stdout.strip()

    if len(identity) < 2 and os.path.isdir(os.path.join(REPO_DIR, "backend", ".git")):
        for key in ("user.name", "user.email"):
            if key not in identity:
                result = subprocess.run(
                    ["git", "-C", os.path.join(REPO_DIR, "backend"), "config", "--get", key],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and result.stdout.strip():
                    identity[key] = result.stdout.strip()
    return identity

def get_last_date():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return f.read().strip()
    return None

def save_last_date(date_str):
    with open(STATE_FILE, "w") as f:
        f.write(f"{date_str}\n")


def get_next_date():
    """Return the next commit date in the configured 2024 date range."""
    last = get_last_date()
    if not last:
        return START_DATE

    try:
        next_date = datetime.fromisoformat(last) + timedelta(days=1)
    except ValueError:
        print(f"Invalid date in {STATE_FILE}: {last}")
        sys.exit(1)

    if next_date > END_DATE:
        print("No commit dates remain in the configured 2024 range.")
        sys.exit(0)
    return next_date

def main():
    date = get_next_date()
    date_str = date.isoformat(timespec="seconds")
    print(f"Using commit date: {date_str}")

    message = input("Commit message (describe what you actually changed): ").strip()
    if not message:
        print("Commit message can't be empty.")
        sys.exit(1)

    subprocess.run(["git", "add", "."], cwd=REPO_DIR, check=True)

    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
    )
    if not staged.stdout.strip():
        print("Nothing changed/staged — pushing the existing commit.")
    else:
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = date_str
        env["GIT_COMMITTER_DATE"] = date_str
        identity = get_git_identity()
        if "user.name" in identity:
            env["GIT_AUTHOR_NAME"] = identity["user.name"]
            env["GIT_COMMITTER_NAME"] = identity["user.name"]
        if "user.email" in identity:
            env["GIT_AUTHOR_EMAIL"] = identity["user.email"]
            env["GIT_COMMITTER_EMAIL"] = identity["user.email"]

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_DIR,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout, result.stderr)
            sys.exit(1)

        save_last_date(date_str)

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
    )
    if remote.returncode != 0:
        print(f"Committed with date {date_str}; no 'origin' remote is configured, so nothing was pushed.")
        return

    # Push the current commit to the remote main branch, even when the local
    # branch has a different name.
    subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=REPO_DIR, check=True)
    print(f"Committed and pushed to main with date {date_str}")

if __name__ == "__main__":
    main()
