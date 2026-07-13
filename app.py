from __future__ import annotations

from pathlib import Path

from account_rotation import run_account_session, run_rotation
from app_config import apply_interval_override, load_rotation_config, parse_args


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    config = load_rotation_config(config_path)
    apply_interval_override(config, args.interval_hours)

    if args.test_rotation:
        if args.keep_open and not args.headless:
            raise ValueError("--keep-open cannot be used with --test-rotation.")
        run_rotation(
            args,
            config["accounts"],
            interval_hours=0,
            max_runs=len(config["accounts"]),
        )
        return

    run_once = args.once or bool(args.account.strip())
    if run_once:
        first_account = config["accounts"][0]
        account = args.account.strip() or first_account["account"]
        password = args.password or first_account["password"]
        success = run_account_session(args, account, password)
        if not success:
            raise SystemExit(1)
        return

    if args.keep_open and not args.headless:
        raise ValueError("--keep-open cannot be used with continuous rotation.")

    try:
        run_rotation(args, config["accounts"], config["interval_hours"])
    except KeyboardInterrupt:
        print("\nRotation stopped by user.")


if __name__ == "__main__":
    main()
