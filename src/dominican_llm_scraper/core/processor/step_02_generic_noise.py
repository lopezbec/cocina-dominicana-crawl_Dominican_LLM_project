import re


def remove_generic_noise(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append(line)
            continue
        if re.fullmatch(r"(saltar a|saltar al|skip to)\b.*", stripped, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"(in english|en español|english|español)", stripped, flags=re.IGNORECASE):
            continue
        if re.fullmatch(
            r"(saltar a:|skip to:|contenido|table of contents)",
            stripped,
            flags=re.IGNORECASE,
        ):
            continue
        if re.fullmatch(r"(mostrar|show)\b.*[↓▲▼].*", stripped, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"[-*•]+", stripped):
            continue
        if re.fullmatch(r"[—–―‑─]{2,}", stripped):
            continue
        lines.append(line)
    return "\n".join(lines)
