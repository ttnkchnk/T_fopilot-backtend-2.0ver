from datetime import date
from typing import List
import logging
from urllib.parse import urlparse
import re
from html import unescape

import httpx
from html.parser import HTMLParser

from core.config import settings
from services.legal_ai_service import LegalAIService
from services.legal_repository import LegalRepository
from google.api_core.exceptions import ResourceExhausted

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk,ru;q=0.9,en;q=0.8",
}

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str):
        if data and data.strip():
            self.parts.append(data.strip())

    def get_text(self) -> str:
        return "\n".join(self.parts)


class LegalIngestService:
    @staticmethod
    def _parse_feed_urls() -> List[str]:
        raw = (settings.LEGAL_FEED_URLS or "").strip()
        # Дозволяємо роздільники , ; \ або переноси рядків
        normalized = raw.replace("\\", ",").replace(";", ",").replace("\n", ",")
        urls = []
        for u in normalized.split(","):
            u = u.strip()
            if not u:
                continue
            parsed = urlparse(u)
            if parsed.scheme not in {"http", "https"}:
                logger.warning(f"Skip URL without http/https scheme: {u}")
                continue
            urls.append(u)
        return urls

    @staticmethod
    def _extract_title(html: str, url: str) -> str:
        """Пробуємо взяти <title> з HTML, інакше робимо охайний fallback."""
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if m:
            title = unescape(m.group(1)).strip()
            title = re.sub(r"\s+", " ", title)
            return title

        parsed = urlparse(url)
        return f"{parsed.netloc} – оновлення для ФОП"

    @staticmethod
    def _detect_source_name(url: str) -> str:
        domain = urlparse(url).netloc.lower()
        if "dtkt.ua" in domain:
            return "Дебет-Кредит"
        if "7eminar.ua" in domain:
            return "7eminar"
        if "factor.academy" in domain:
            return "Factor Academy"
        if "tax.gov.ua" in domain:
            return "ДПС України"
        return domain

    @staticmethod
    async def ingest_feeds() -> None:
        urls = LegalIngestService._parse_feed_urls()
        if not urls:
            logger.warning("LEGAL_FEED_URLS is empty, nothing to ingest")
            return

        async with httpx.AsyncClient(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
            for url in urls:
                try:
                    logger.info(f"Ingesting legal feed from {url}")
                    resp = await client.get(url)
                    if resp.status_code == 403:
                        logger.warning(f"Forbidden (403) for {url}, skipping")
                        continue

                    resp.raise_for_status()

                    html_raw = resp.text
                    text = html_raw
                    if len(text) > 20000:
                        text = text[:20000]

                    # Очищення HTML до тексту (без зовнішніх залежностей)
                    try:
                        parser = _TextExtractor()
                        parser.feed(text)
                        cleaned_text = parser.get_text()
                    except Exception:
                        cleaned_text = text

                    title = LegalIngestService._extract_title(html_raw, url)
                    source_name = LegalIngestService._detect_source_name(url)

                    update = LegalAIService.classify_and_summarize(
                        title=title,
                        text=cleaned_text,
                        source=source_name,
                        url=url,
                        law_date=date.today(),
                    )

                    doc_id = LegalRepository.upsert_by_url(update)
                    logger.info(f"Saved legal update from {url} -> {doc_id}")
                except ResourceExhausted as e:
                    logger.warning(f"Gemini quota exceeded: {e}; skip {url}")
                    continue
                except httpx.HTTPStatusError as e:
                    logger.warning(f"Failed to fetch {url}: {e}")
                    continue
                except Exception as e:
                    logger.exception(f"Failed to ingest {url}: {e}")
