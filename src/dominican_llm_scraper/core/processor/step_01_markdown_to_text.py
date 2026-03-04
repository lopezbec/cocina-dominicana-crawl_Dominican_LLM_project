import mistune
from bs4 import BeautifulSoup


def markdown_to_text(markdown_content: str) -> str:
    html = mistune.create_markdown(renderer="html")(markdown_content)
    html = str(html)
    return BeautifulSoup(html, "html.parser").get_text(separator="\n")
