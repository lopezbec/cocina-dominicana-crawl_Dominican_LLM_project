import re


def join_wrapped_lines(text: str) -> str:
    lines = text.split("\n")
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            output.append(line)
            i += 1
            continue

        current = line.rstrip()
        if i + 1 < len(lines):
            next_index = i + 1
            skip_blank = False
            if next_index < len(lines) and not lines[next_index].strip():
                next_index += 1
                skip_blank = True
            if next_index < len(lines):
                next_line = lines[next_index]
                if next_line.strip() and _should_join(current, next_line, skip_blank):
                    output.append(f"{current} {next_line.strip()}")
                    i = next_index + 1
                    continue

        output.append(current)
        i += 1

    return "\n".join(output)


def _should_join(current: str, next_line: str, skip_blank: bool) -> bool:
    if _is_list_line(current) or _is_list_line(next_line):
        return False
    if re.search(r"[.!?]$", current.strip()):
        return False
    if re.match(r"^[,.;:!?\)\]\}]+", next_line.strip()):
        return True
    if re.search(r"[\(\[\{]$", current.strip()):
        return True
    if skip_blank:
        if re.match(r"^[,.;:!?\)\]\}]+", next_line.strip()):
            return True
        return bool(re.match(r"^[a-záéíóúñü]", next_line.strip()))
    if not re.match(r"^[a-záéíóúñü]", next_line.strip(), flags=re.IGNORECASE):
        return False
    return True


def _is_list_line(line: str) -> bool:
    return bool(re.match(r"^\s*(?:[-*•]|\d+\.)\s+", line))
