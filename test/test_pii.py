from app.policy.pii import redact

text = "Contact me at test@example.com or call 555-123-4567."
redacted, summary = redact(text)
print(redacted)
print(summary)