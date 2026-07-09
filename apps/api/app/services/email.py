"""Email backend abstraction: console (local), SES, or Resend.

Every send sets List-Unsubscribe headers — a Gmail deliverability requirement
since 2024 (ARCHITECTURE §8). In local dev we just log the message so the whole
subscribe/broadcast loop runs with no email provider configured.
"""

from __future__ import annotations

import logging

from app.config import settings

log = logging.getLogger("shiplog.email")


async def send_email(
    *, to: str, subject: str, html: str, list_unsubscribe: str | None = None
) -> None:
    headers = {}
    if list_unsubscribe:
        headers["List-Unsubscribe"] = f"<{list_unsubscribe}>"
        headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    if settings.email_backend == "console":
        log.info("EMAIL → %s | %s\n%s", to, subject, html)
        return

    if settings.email_backend == "ses":
        import boto3  # lazy import: keep Lambda cold start lean

        client = boto3.client("ses")
        client.send_email(
            Source=settings.email_from,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": html}},
            },
        )
        return

    if settings.email_backend == "resend":
        import httpx

        async with httpx.AsyncClient(timeout=10) as http:
            await http.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.email_from,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                    "headers": headers,
                },
            )
        return

    raise ValueError(f"Unknown email backend: {settings.email_backend}")
