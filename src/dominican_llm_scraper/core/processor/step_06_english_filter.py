import re

from wordfreq import zipf_frequency

_EN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "for",
    "from",
    "he",
    "her",
    "his",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "not",
    "of",
    "on",
    "or",
    "our",
    "she",
    "so",
    "that",
    "the",
    "their",
    "then",
    "these",
    "they",
    "this",
    "those",
    "to",
    "was",
    "we",
    "were",
    "with",
    "you",
    "your",
}


def filter_english_words(text: str) -> str:
    token_pattern = re.compile(r"\b[\w\u00C0-\u017F]+\b|\S")
    word_pattern = re.compile(r"\b[\w\u00C0-\u017F]+\b")

    filtered_lines = []
    for line in text.split("\n"):
        if not line.strip():
            filtered_lines.append(line)
            continue

        kept = []
        for token in token_pattern.findall(line):
            if not word_pattern.match(token):
                kept.append(token)
                continue

            lowered = token.lower()

            if lowered in _EN_STOPWORDS:
                continue

            if len(token) <= 2:
                kept.append(token)
                continue

            if token[0].isupper():
                kept.append(token)
                continue

            if re.search(r"[áéíóúñüÁÉÍÓÚÑÜ]", token):
                kept.append(token)
                continue

            en_zipf = zipf_frequency(lowered, "en")
            es_zipf = zipf_frequency(lowered, "es")

            if es_zipf >= 3.5:
                kept.append(token)
                continue

            if not (en_zipf >= 2.5 and (en_zipf - es_zipf) >= 1.0):
                kept.append(token)

        joined = " ".join(kept)
        joined = re.sub(r"\s+([.,;:!?)])", r"\1", joined)
        joined = re.sub(r"([¿¡(])\s+", r"\1", joined)
        joined = re.sub(r" {2,}", " ", joined)
        if joined.strip():
            filtered_lines.append(joined)

    return "\n".join(filtered_lines)
