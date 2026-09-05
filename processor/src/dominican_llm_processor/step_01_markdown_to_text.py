import mistune
from bs4 import BeautifulSoup


MARKDOWN_RENDERER = mistune.create_markdown(renderer="html", plugins=["table"])


def markdown_to_text(markdown_content: str) -> str:
    html = MARKDOWN_RENDERER(markdown_content)
    html = str(html)
    return BeautifulSoup(html, "html.parser").get_text(separator="\n")
