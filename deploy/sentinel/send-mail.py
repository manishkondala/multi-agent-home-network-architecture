#!/usr/bin/env python3
"""send-mail.py <subject>  (body on stdin) — mail the owner via Gmail SMTP (free, app password).
Creds: /home/pi/pi-fleet/secrets/smtp.env -> GMAIL_USER, GMAIL_APP_PASSWORD, MAIL_TO.
No creds yet -> queue the mail in sentinel/outbox/ and exit 0 (nothing is lost)."""
import sys, os, smtplib, ssl, time
from email.message import EmailMessage

SENTINEL = "/home/pi/pi-fleet/sentinel"
ENV = "/home/pi/pi-fleet/secrets/smtp.env"

subject = sys.argv[1] if len(sys.argv) > 1 else "[pi-fleet] (no subject)"
body = sys.stdin.read()

cfg = {}
if os.path.exists(ENV):
    for line in open(ENV):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            cfg[k] = v.strip().strip('"')

user, pw = cfg.get("GMAIL_USER"), cfg.get("GMAIL_APP_PASSWORD")
to = cfg.get("MAIL_TO", "kondalamanish@gmail.com")

if not (user and pw):
    os.makedirs(f"{SENTINEL}/outbox", exist_ok=True)
    fn = f"{SENTINEL}/outbox/{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.eml"
    with open(fn, "w") as f:
        f.write(f"Subject: {subject}\n\n{body}")
    print(f"send-mail: no SMTP creds ({ENV} missing GMAIL_USER/GMAIL_APP_PASSWORD); queued {fn}")
    sys.exit(0)

msg = EmailMessage()
msg["Subject"], msg["From"], msg["To"] = subject, user, to
msg.set_content(body)
try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as s:
        s.login(user, pw)
        s.send_message(msg)
    print(f"send-mail: sent '{subject}' to {to}")
except Exception as e:
    os.makedirs(f"{SENTINEL}/outbox", exist_ok=True)
    fn = f"{SENTINEL}/outbox/{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-failed.eml"
    with open(fn, "w") as f:
        f.write(f"Subject: {subject}\nX-Error: {e}\n\n{body}")
    print(f"send-mail: FAILED ({e}); queued {fn}")
    sys.exit(1)
