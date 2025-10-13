from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime

class ArticleMetadata(BaseModel):
    title: str
    url: str
    publish_date: Optional[str] = None
    review_date: Optional[str] = None
    word_count: Optional[int] = None
    recommendations: List[str] = []
    section: str
    slug: str

class ScrapedArticle(BaseModel):
    metadata: ArticleMetadata
    content: str
    comments: str
    scraped_at: datetime
    
class ScrapingStats(BaseModel):
    total_articles: int
    successful_scrapes: int
    failed_scrapes: int
    sections_completed: List[str]
    duration_seconds: float
    errors: List[str] = []

class ProgressState(BaseModel):
    completed_urls: List[str] = []
    failed_urls: List[str] = []
    current_section: Optional[str] = None
    total_found: int = 0
    total_scraped: int = 0