import re


def cleanup_inline_punctuation(text: str) -> str:
    text = re.sub(r"(^|(?<=\s))[*_`]+(?=\s|$)", "", text)
    text = re.sub(r" {2,}", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()
