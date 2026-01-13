"""Entry point for python -m dominican_llm_scraper"""

from dominican_llm_scraper.cli.commands import main
import sys

if __name__ == "__main__":
    sys.exit(main())
