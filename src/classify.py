"""Turn a raw Gmail message into a channel + sender.

Gmail is used as a universal adapter: LinkedIn and Teams notification emails
are reclassified into their own channel so the dashboard shows them under
LinkedIn / Teams instead of Email. Slack's own notification emails are dropped
because Slack is polled directly (avoids duplicates).
"""
import re

LINKEDIN_SUBJECT_PATTERNS = [
    re.compile(r"^(.+?) sent you a message", re.I),
    re.compile(r"^(.+?) just messaged you", re.I),
    re.compile(r"new message from (.+)$", re.I),
    re.compile(r"^(.+?) replied to your message", re.I),
    re.compile(r"^message from (.+?):", re.I),
]


def parse_from_header(raw):
    """'Name <a@b.com>' -> (name, email)."""
    m = re.match(r'^\s*"?([^"<]*)"?\s*<([^>]+)>', raw or "")
    if m:
        name = m.group(1).strip() or m.group(2)
        return name, m.group(2).strip().lower()
    addr = (raw or "").strip().lower()
    return addr, addr


def classify(from_name, from_email, subject):
    """Returns (channel, sender_name) or None when the email should be skipped."""
    domain = from_email.rsplit("@", 1)[-1]

    if "slack.com" in domain:
        return None  # polled natively

    if "linkedin.com" in domain:
        for pat in LINKEDIN_SUBJECT_PATTERNS:
            m = pat.search(subject or "")
            if m:
                return "linkedin", m.group(1).strip()
        # Other LinkedIn mail (invites, digests, job alerts) stays out of the feed
        return None

    if "teams.microsoft.com" in domain or domain == "email.teams.microsoft.com":
        return "teams", from_name.replace("(via Microsoft Teams)", "").strip() or "Microsoft Teams"

    return "email", from_name
