# utils/emailer_resend.py
import json
import os
import urllib.error
import urllib.request


def send_email_resend(to, subject, html, text, *, reply_to=None, timeout=15):
    """
    Dependency-free Resend email sender.
    """
    api_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set")

    sender = (os.environ.get("RESEND_FROM") or "").strip()
    if not sender:
        raise RuntimeError("RESEND_FROM is not set")

    # Normalize recipients
    if isinstance(to, str):
        to_list = [to]
    else:
        to_list = list(to)

    payload = {
        "from": sender,
        "to": to_list,
        "subject": subject,
        "html": html,
        "text": text,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Resend HTTPError {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Resend URLError: {e}") from e
