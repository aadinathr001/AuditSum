from dataclasses import dataclass


@dataclass
class PolicyDecision:
    check_name: str
    outcome: str  # 'allow', 'deny', 'redact', 'flag'
    reason: str
    details: dict | None = None


def check_size(text: str, max_chars: int = 250_000) -> PolicyDecision:
    size = len(text)
    if size > max_chars:
        return PolicyDecision(
            check_name="size_limit",
            outcome="deny",
            reason=f"document is {size} characters, limit is {max_chars}",
            details={"size": size, "limit": max_chars},
        )
    return PolicyDecision(
        check_name="size_limit",
        outcome="allow",
        reason="within size limit",
        details={"size": size, "limit": max_chars},
    )


def check_file_type(filename: str, allowed_extensions: tuple[str, ...] = (".txt", ".md")) -> PolicyDecision:
    if not filename.lower().endswith(allowed_extensions):
        return PolicyDecision(
            check_name="file_type",
            outcome="deny",
            reason=f"'{filename}' has a disallowed extension",
            details={"filename": filename, "allowed": list(allowed_extensions)},
        )
    return PolicyDecision(
        check_name="file_type",
        outcome="allow",
        reason="allowed file type",
        details={"filename": filename},
    )


def evaluate(session, text: str, filename: str, model: str) -> list[PolicyDecision]:
    return [
        check_kill_switch(session, model),
        check_file_type(filename),
        check_size(text),
        check_pii(text),
    ]

def check_kill_switch(session, model: str) -> PolicyDecision:
    from app.models import Control  # imported here to avoid a circular import

    control = session.get(Control, f"model:{model}:enabled")

    if control is not None and control.value == "false":
        return PolicyDecision(
            check_name="kill_switch",
            outcome="deny",
            reason=f"model '{model}' is currently disabled by an admin",
            details={"model": model},
        )

    return PolicyDecision(
        check_name="kill_switch",
        outcome="allow",
        reason=f"model '{model}' is enabled",
        details={"model": model},
    )

def check_pii(text: str) -> PolicyDecision:
    from app.policy.pii import find_emails, find_phones

    emails = find_emails(text)
    phones = find_phones(text)

    if emails or phones:
        return PolicyDecision(
            check_name="pii_scan",
            outcome="redact",
            reason=f"found {len(emails)} email(s) and {len(phones)} phone number(s)",
            details={"emails_found": len(emails), "phones_found": len(phones)},
        )

    return PolicyDecision(
        check_name="pii_scan",
        outcome="allow",
        reason="no PII detected",
        details={"emails_found": 0, "phones_found": 0},
    )