from app.pipeline.chunker import chunk_text

# A short text - should produce exactly one chunk
short_text = "This is a short document. " * 50
chunks = chunk_text(short_text)
print(f"Short text: {len(chunks)} chunk(s)")

# A long text - should produce multiple chunks
long_text = "This is sentence number {}. " * 1
long_text = "".join(f"This is paragraph {i}.\n\n" for i in range(2000))
chunks = chunk_text(long_text)
print(f"Long text: {len(chunks)} chunk(s), total length {len(long_text)}")

for i, c in enumerate(chunks):
    print(f"  chunk {i}: chars {c.char_start}-{c.char_end} ({len(c.text)} chars)")

# Verify every character of the original text is covered by at least one chunk
covered = set()
for c in chunks:
    covered.update(range(c.char_start, c.char_end))
print(f"Coverage: {len(covered)} / {len(long_text)} characters covered")