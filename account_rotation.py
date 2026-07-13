from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta

from mimo_workflow import run_workflow
from nodriver_utils import build_browser, error_summary


async def keep_browser_available(args: argparse.Namespace) -> None:
    if args.keep_open and not args.headless:
        print("Chrome is being kept open. Close it manually when done.")
        return
    if not args.headless and args.stay_seconds > 0:
        print(f"Keeping browser open for {args.stay_seconds} seconds...")
        await asyncio.sleep(args.stay_seconds)


async def run_account_session(
    args: argparse.Namespace, account: str, password: str
) -> bool:
    args.account = account
    args.password = password
    browser = None
    try:
        browser = await build_browser(args.headless)
        tab = await browser.get(args.url)
        completed = await run_workflow(browser, tab, args)
        await keep_browser_available(args)
        return completed
    except Exception as error:
        print(f"Account session failed: {error_summary(error)}")
        return False
    finally:
        if browser is not None and not (args.keep_open and not args.headless):
            try:
                browser.stop()
            except Exception as error:
                print(f"Could not close Chrome cleanly: {error_summary(error)}")


async def run_rotation(
    args: argparse.Namespace,
    accounts: list[dict[str, str]],
    interval_hours: float,
    max_runs: int | None = None,
) -> None:
    interval_seconds = interval_hours * 60 * 60
    account_index = 0
    runs_completed = 0
    loop = asyncio.get_running_loop()
    next_run = loop.time()

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
        completed = await run_account_session(
            args, account, account_data["password"]
        )
        print(f"Account session {'completed' if completed else 'failed'}: {account}")

        runs_completed += 1
        account_index = (account_index + 1) % len(accounts)
        if max_runs is not None and runs_completed >= max_runs:
            print(f"Test rotation finished after {runs_completed} account session(s).")
            return

        next_run += interval_seconds
        wait_seconds = max(0.0, next_run - loop.time())
        next_run_at = datetime.now().astimezone() + timedelta(seconds=wait_seconds)
        print(
            f"Next account: {accounts[account_index]['account']} at "
            f"{next_run_at.isoformat(timespec='seconds')} "
            f"(in {wait_seconds / 3600:.2f} hours)."
        )
        await asyncio.sleep(wait_seconds)
