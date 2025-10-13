"""
Complete Dominican Culture Scraper using Firecrawl - Version 2
Includes rate limiting and retry logic
"""

from firecrawl import Firecrawl
import os
import re
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DominicanCultureScraperV2:
    def __init__(self):
        self.api_key = os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY not found in environment")
        
        self.firecrawl = Firecrawl(api_key=self.api_key)
        self.base_url = "https://www.cocinadominicana.com"
        
        # Define the 4 main culture sections
        self.sections = {
            "cultura_origenes": {
                "name": "Cultura y Orígenes",
                "url": f"{self.base_url}/cultura/herencia",
                "directory": "cultura_origenes"
            },
            "tradiciones_costumbres": {
                "name": "Tradiciones y Costumbres", 
                "url": f"{self.base_url}/cultura/tradiciones-costumbres",
                "directory": "tradiciones_costumbres"
            },
            "festividades_celebraciones": {
                "name": "Festividades y Celebraciones",
                "url": f"{self.base_url}/cultura/celebraciones", 
                "directory": "festividades_celebraciones"
            },
            "comparaciones": {
                "name": "Comparaciones",
                "url": f"{self.base_url}/cultura/versus",
                "directory": "comparaciones"
            }
        }
        
        # Create output directory structure
        self.output_dir = Path("scraped_content")
        self.output_dir.mkdir(exist_ok=True)
        
        for section_info in self.sections.values():
            section_dir = self.output_dir / section_info["directory"]
            section_dir.mkdir(exist_ok=True)
    
    def safe_scrape(self, url: str, max_retries: int = 3, base_delay: int = 20) -> Optional[object]:
        """Safely scrape with rate limiting and retry logic"""
        for attempt in range(max_retries):
            try:
                doc = self.firecrawl.scrape(url, formats=["markdown"])
                return doc
                
            except Exception as e:
                error_msg = str(e)
                
                if "Rate Limit Exceeded" in error_msg:
                    # Extract wait time from error message
                    wait_time = base_delay
                    if "retry after" in error_msg:
                        try:
                            match = re.search(r'retry after (\d+)s', error_msg)
                            if match:
                                wait_time = int(match.group(1))
                        except:
                            pass
                    
                    print(f"⏳ Rate limit hit. Waiting {wait_time + 5} seconds...")
                    time.sleep(wait_time + 5)  # Add 5 seconds buffer
                    
                    if attempt < max_retries - 1:
                        print(f"🔄 Retrying {url} (attempt {attempt + 2}/{max_retries})")
                        continue
                
                print(f"❌ Error scraping {url} (attempt {attempt + 1}): {error_msg}")
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"⏳ Waiting {delay}s before retry...")
                    time.sleep(delay)
        
        return None
    
    def extract_article_urls(self, section_url: str) -> List[str]:
        """Extract all article URLs from a section page"""
        print(f"📥 Extracting article URLs from: {section_url}")
        
        doc = self.safe_scrape(section_url)
        if not doc:
            print("❌ Failed to scrape section page")
            return []
            
        # Check if document has markdown content
        if not hasattr(doc, 'markdown') or not getattr(doc, 'markdown', None):
            print("❌ No markdown content found")
            return []
        
        markdown_content = getattr(doc, 'markdown')
        
        # Extract URLs using regex patterns
        patterns = [
            r'\](https://www\.cocinadominicana\.com/([^)]+))\)',
            r'\((https://www\.cocinadominicana\.com/([^)]+))\)',
        ]
        
        all_urls = set()
        for pattern in patterns:
            matches = re.findall(pattern, markdown_content)
            for match in matches:
                if isinstance(match, tuple):
                    url = match[0] if match[0].startswith('http') else f"{self.base_url}/{match[0]}"
                    url_path = match[1] if match[0].startswith('http') else match[0]
                else:
                    url = match if match.startswith('http') else f"{self.base_url}/{match}"
                    url_path = match.replace(self.base_url + '/', '')
                
                # Filter valid article URLs
                if (not url.endswith(('.jpg', '.png', '.gif', '.jpeg')) and 
                    '/cultura/' not in url and
                    '#' not in url and
                    'dominicancooking.com' not in url and
                    'wp-content' not in url and
                    url_path and 
                    url_path not in ['cultura/herencia', 'cultura/tradiciones-costumbres', 
                                   'cultura/celebraciones', 'cultura/versus'] and
                    url != section_url):
                    all_urls.add(url)
        
        article_urls = sorted(list(all_urls))
        print(f"✅ Found {len(article_urls)} article URLs")
        return article_urls
    
    def scrape_article(self, url: str) -> Optional[Dict]:
        """Scrape an individual article"""
        print(f"📄 Scraping: {url}")
        
        doc = self.safe_scrape(url)
        if not doc:
            print(f"❌ Failed to scrape {url}")
            return None
            
        # Check if document has markdown content
        if not hasattr(doc, 'markdown') or not getattr(doc, 'markdown', None):
            print(f"❌ No content found for {url}")
            return None
        
        markdown_content = getattr(doc, 'markdown')
        
        # Extract metadata
        title = "Unknown Title"
        description = ""
        if hasattr(doc, 'metadata'):
            metadata = getattr(doc, 'metadata')
            if metadata:
                title = getattr(metadata, 'title', 'Unknown Title')
                description = getattr(metadata, 'description', '')
        
        # Clean the URL slug for filename
        url_slug = url.replace(self.base_url + '/', '').replace('/', '_')
        
        # Calculate some stats
        word_count = len(markdown_content.split())
        char_count = len(markdown_content)
        
        article_data = {
            "title": title,
            "description": description,
            "url": url,
            "url_slug": url_slug,
            "scraped_at": datetime.now().isoformat(),
            "word_count": word_count,
            "char_count": char_count,
            "content": markdown_content
        }
        
        print(f"✅ Scraped: {title} ({word_count} words)")
        return article_data
    
    def save_article(self, article_data: Dict, section_directory: str):
        """Save article to file"""
        if not article_data:
            return
        
        section_dir = self.output_dir / section_directory
        
        # Create safe filename
        safe_filename = re.sub(r'[^\w\-_.]', '_', article_data['url_slug'])
        safe_filename = safe_filename[:100]  # Limit length
        
        # Save markdown content
        content_file = section_dir / f"{safe_filename}.md"
        with open(content_file, 'w', encoding='utf-8') as f:
            # Write frontmatter
            f.write("---\n")
            f.write(f"title: \"{article_data['title']}\"\n")
            if article_data['description']:
                f.write(f"description: \"{article_data['description']}\"\n")
            f.write(f"url: {article_data['url']}\n")
            f.write(f"scraped_at: {article_data['scraped_at']}\n")
            f.write(f"word_count: {article_data['word_count']}\n")
            f.write(f"char_count: {article_data['char_count']}\n")
            f.write("---\n\n")
            f.write(article_data['content'])
        
        # Save metadata as JSON
        metadata_file = section_dir / f"{safe_filename}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            # Don't include content in JSON to avoid duplication
            metadata = {k: v for k, v in article_data.items() if k != 'content'}
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved: {content_file.name}")
    
    def scrape_section(self, section_key: str):
        """Scrape all articles from a section"""
        section_info = self.sections[section_key]
        print(f"\n🔥 STARTING SECTION: {section_info['name']}")
        print("=" * 60)
        
        # Extract article URLs
        article_urls = self.extract_article_urls(section_info['url'])
        
        if not article_urls:
            print(f"❌ No articles found in {section_info['name']}")
            return
        
        print(f"📚 Found {len(article_urls)} articles to scrape")
        
        # Scrape each article
        scraped_count = 0
        failed_count = 0
        
        for i, url in enumerate(article_urls, 1):
            print(f"\n[{i}/{len(article_urls)}] ", end="")
            
            # Check if already scraped
            url_slug = url.replace(self.base_url + '/', '').replace('/', '_')
            safe_filename = re.sub(r'[^\w\-_.]', '_', url_slug)[:100]
            section_dir = self.output_dir / section_info['directory']
            content_file = section_dir / f"{safe_filename}.md"
            
            if content_file.exists():
                print(f"⏭️  Skipping (already scraped): {url}")
                scraped_count += 1
                continue
            
            # Scrape article
            article_data = self.scrape_article(url)
            
            if article_data:
                # Save article
                self.save_article(article_data, section_info['directory'])
                scraped_count += 1
            else:
                failed_count += 1
            
            # Rate limiting - be more conservative
            print("⏳ Waiting 3s...")
            time.sleep(3)
        
        print(f"\n✅ SECTION COMPLETE: {section_info['name']}")
        print(f"   Scraped: {scraped_count}")
        print(f"   Failed: {failed_count}")
        print(f"   Total: {len(article_urls)}")
    
    def scrape_all_sections(self):
        """Scrape all sections"""
        start_time = datetime.now()
        
        print("🇩🇴 DOMINICAN CULTURE SCRAPER V2 STARTING")
        print("=" * 60)
        print(f"Start time: {start_time}")
        print(f"Output directory: {self.output_dir.absolute()}")
        print(f"Sections to scrape: {len(self.sections)}")
        print("⚡ Features: Rate limiting, retry logic, resume capability")
        
        total_scraped = 0
        total_failed = 0
        
        for section_key in self.sections:
            try:
                self.scrape_section(section_key)
                
                # Count files in section
                section_dir = self.output_dir / self.sections[section_key]['directory']
                md_files = list(section_dir.glob("*.md"))
                total_scraped += len(md_files)
                
            except Exception as e:
                print(f"❌ Error in section {section_key}: {e}")
                total_failed += 1
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        print(f"\n🎉 SCRAPING COMPLETE!")
        print("=" * 60)
        print(f"Duration: {duration}")
        print(f"Total articles scraped: {total_scraped}")
        print(f"Total sections failed: {total_failed}")
        print(f"Output directory: {self.output_dir.absolute()}")
        
        # Create summary file
        summary = {
            "scraping_session": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration.total_seconds(),
                "total_articles_scraped": total_scraped,
                "total_sections_failed": total_failed
            },
            "sections": {}
        }
        
        for section_key, section_info in self.sections.items():
            section_dir = self.output_dir / section_info['directory']
            md_files = list(section_dir.glob("*.md"))
            summary["sections"][section_key] = {
                "name": section_info['name'],
                "url": section_info['url'],
                "articles_scraped": len(md_files),
                "directory": section_info['directory']
            }
        
        summary_file = self.output_dir / "scraping_summary_v2.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"📊 Summary saved to: {summary_file}")

if __name__ == "__main__":
    scraper = DominicanCultureScraperV2()
    scraper.scrape_all_sections()