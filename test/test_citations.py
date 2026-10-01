from app.pipeline.citations import verify_quote

source = "The quick brown fox jumps over the lazy dog. It was a sunny day."

# A real quote - should verify
print(verify_quote(source, "quick brown fox"))

# A fabricated quote - should fail
print(verify_quote(source, "the dog was actually a cat"))

# A real quote with different whitespace - should still verify thanks to normalization
print(verify_quote(source, "quick   brown\nfox"))