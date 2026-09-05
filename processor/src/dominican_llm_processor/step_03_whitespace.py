import re


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # Normalize all newlines to \n
    text = re.sub(r"[ \t]+", " ", text)  # Replace multiple spaces/tabs with single space
    text = re.sub(r"\n{3,}", "\n\n", text)  # Replace 3+ newlines with 2
    lines = [line.rstrip() for line in text.split("\n")]  # Remove trailing whitespace from each line
    return "\n".join(lines).strip()
