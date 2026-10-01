from app.policy.engine import evaluate

# A normal, small text file - should all pass
decisions = evaluate("Hello world", "notes.txt")
for d in decisions:
    print(d)

print("---")

# A disallowed file type
decisions = evaluate("Hello world", "notes.pdf")
for d in decisions:
    print(d)

print("---")

# Too large
decisions = evaluate("x" * 300_000, "big.txt")
for d in decisions:
    print(d)