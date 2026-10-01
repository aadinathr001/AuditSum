import unicodedata
import re


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def verify_quote(source_text: str, quote: str) -> tuple[bool, int | None, int | None]:
    normalized_source = normalize(source_text)
    normalized_quote = normalize(quote)

    position = normalized_source.find(normalized_quote)

    if position == -1:
        return False, None, None

    return True, position, position + len(normalized_quote)