"""Entry point for the cron job: polls every configured channel.

Each poller runs independently — one failing doesn't block the others —
and reports its health to the connections table for the dashboard.
"""
from . import db, gmail_poller, slack_poller

POLLERS = {
    "gmail": gmail_poller.poll,
    "slack": slack_poller.poll,
}


def main():
    failures = []
    for channel, poll in POLLERS.items():
        try:
            if poll() is None:
                continue  # credentials not configured yet — leave status 'pending'
            db.mark_connection(channel, "ok")
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"{channel}: ERROR {e}")
            db.mark_connection(channel, "error", error=str(e)[:500])
            failures.append(channel)
    if failures:
        raise SystemExit(f"pollers failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
