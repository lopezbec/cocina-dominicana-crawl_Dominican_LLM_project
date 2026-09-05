from typing import Dict, Tuple

from dominican_llm_processor.step_01_markdown_to_text import markdown_to_text
from dominican_llm_processor.step_02_generic_noise import remove_generic_noise
from dominican_llm_processor.step_03_whitespace import normalize_whitespace
from dominican_llm_processor.step_04_line_joiner import join_wrapped_lines
from dominican_llm_processor.step_05_inline_punctuation import cleanup_inline_punctuation


def process_markdown_to_plain_text(markdown_content: str) -> Tuple[Dict, str]:
    text = markdown_to_text(markdown_content)
    text = remove_generic_noise(text)
    text = normalize_whitespace(text)
    text = join_wrapped_lines(text)
    text = cleanup_inline_punctuation(text)
    return {}, text
