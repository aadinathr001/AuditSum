import re

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")


def find_emails(text: str) -> list[str]:
    return EMAIL_PATTERN.findall(text)


def find_phones(text: str) -> list[str]:
    return PHONE_PATTERN.findall(text)


def redact(text: str) -> tuple[str, dict]:
    emails = find_emails(text)
    phones = find_phones(text)

    redacted = text
    for i, email in enumerate(set(emails), start=1):
        redacted = redacted.replace(email, f"[EMAIL_{i}]")
    for i, phone in enumerate(set(phones), start=1):
        redacted = redacted.replace(phone, f"[PHONE_{i}]")

    return redacted, {"emails_found": len(emails), "phones_found": len(phones)}