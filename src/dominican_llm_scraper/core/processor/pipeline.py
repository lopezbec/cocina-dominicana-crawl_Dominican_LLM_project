from typing import Dict, Tuple

from dominican_llm_scraper.core.processor.step_01_markdown_to_text import markdown_to_text
from dominican_llm_scraper.core.processor.step_02_generic_noise import remove_generic_noise
from dominican_llm_scraper.core.processor.step_03_whitespace import normalize_whitespace
from dominican_llm_scraper.core.processor.step_04_line_joiner import join_wrapped_lines
from dominican_llm_scraper.core.processor.step_05_inline_punctuation import cleanup_inline_punctuation
from dominican_llm_scraper.core.processor.step_06_english_filter import filter_english_words


def process_markdown_to_plain_text(markdown_content: str) -> Tuple[Dict, str]:
    text = markdown_to_text(markdown_content)
    text = remove_generic_noise(text)
    text = normalize_whitespace(text)
    text = join_wrapped_lines(text)
    text = cleanup_inline_punctuation(text)
    text = filter_english_words(text)
    return {}, text
