from __future__ import annotations

import argparse
import time
from datetime import datetime

from mimo_workflow import run_workflow
from selenium_utils import build_driver, error_summary


def keep_browser_available(args: argparse.Namespace) -> None:
    if args.keep_open and not args.headless:
        print("Chrome is being kept open. Close it manually when done.")
        return
    if not args.headless and args.stay_seconds > 0:
        print(f"Keeping browser open for {args.stay_seconds} seconds...")
        time.sleep(args.stay_seconds)


def run_account_session(
    args: argparse.Namespace, account: str, password: str
) -> bool:
    args.account = account
    args.password = password
    driver = build_driver(args.headless, args.keep_open)
    try:
        completed = run_workflow(driver, args)
        keep_browser_available(args)
        return completed
    except Exception as error:
        print(f"Account session failed: {error_summary(error)}")
        return False
    finally:
        if not (args.keep_open and not args.headless):
            driver.quit()


def run_rotation(
    args: argparse.Namespace,
    accounts: list[dict[str, str]],
    interval_hours: float,
    max_runs: int | None = None,
) -> None:
    interval_seconds = interval_hours * 60 * 60
    account_index = 0
    runs_completed = 0
    next_run = time.monotonic()

    if max_runs is None:
        print(
            f"Continuous rotation started with {len(accounts)} account(s), "
            f"one account every {interval_hours:g} hour(s)."
        )
    else:
        print(
            f"Test rotation started: {max_runs} account session(s), "
            "no wait between accounts."
        )
    print("Press Ctrl+C to stop.")

    while True:
        account_data = accounts[account_index]
        account = account_data["account"]
        print(
            f"\n[{datetime.now().astimezone().isoformat(timespec='seconds')}] "
            f"Running account {account_index + 1}/{len(accounts)}: {account}"
        )
        completed = run_account_session(args, account, account_data["password"])
        print(f"Account session {'completed' if completed else 'failed'}: {account}")

        runs_completed += 1
        account_index = (account_index + 1) % len(accounts)
        if max_runs is not None and runs_completed >= max_runs:
            print(f"Test rotation finished after {runs_completed} account session(s).")
            return

        next_run += interval_seconds
        wait_seconds = max(0.0, next_run - time.monotonic())
        next_run_at = datetime.fromtimestamp(time.time() + wait_seconds).astimezone()
        print(
            f"Next account: {accounts[account_index]['account']} at "
            f"{next_run_at.isoformat(timespec='seconds')} "
            f"(in {wait_seconds / 3600:.2f} hours)."
        )
        time.sleep(wait_seconds)
