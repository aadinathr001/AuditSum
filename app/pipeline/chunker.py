from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    char_start: int
    char_end: int


def chunk_text(text: str, target_chars: int = 12_000, overlap_chars: int = 800) -> list[Chunk]:
    if len(text) <= target_chars:
        return [Chunk(text=text, char_start=0, char_end=len(text))]

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + target_chars, len(text))

        if end < len(text):
            paragraph_break = text.rfind("\n\n", start, end)
            if paragraph_break != -1 and paragraph_break > start:
                end = paragraph_break

        chunks.append(Chunk(text=text[start:end], char_start=start, char_end=end))

        if end >= len(text):
            break

        start = max(end - overlap_chars, start + 1)

    return chunks