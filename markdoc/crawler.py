"""
Crawler engine for fetching documentation URLs.
"""

import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session


from markdoc.utils import fetch_markdown
from markdoc.database import SessionLocal, DocContent, DocURL, Task


class CrawlerWorker:
    """Worker class for crawling documentation sites"""

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.should_stop = False

    def _load_task(self, db: Session):
        """Load task from database"""
        return db.query(Task).filter(Task.id == self.task_id).first()

    def _check_status(self, db: Session):
        """Check if task should continue running"""
        task = self._load_task(db)
        if not task:
            return False
        return task.status == "running"

    def _url_matches_patterns(self, url: str, patterns: list[str], pattern_type: str):
        """Check if URL matches any pattern"""
        if not patterns:
            return False

        if pattern_type == "startswith":
            return any(url.startswith(pattern) for pattern in patterns)
        elif pattern_type == "regexp":
            return any(re.match(pattern, url) for pattern in patterns)
        return False

    def _should_process_url(self, url: str, task: Task):
        """Determine if URL should be processed based on patterns

        Logic:
        1. If URL matches any excluded pattern -> exclude
        2. If included patterns exist and URL matches any -> include
        3. If no included patterns specified -> include all (use base_url as default)
        """
        config = json.loads(task.config) if task.config else {}
        included_patterns = config.get("included_patterns", [])
        excluded_patterns = config.get("excluded_patterns", [])
        pattern_type = config.get("pattern_type", "startswith")

        # Check excluded patterns first
        if excluded_patterns and self._url_matches_patterns(
            url, excluded_patterns, pattern_type
        ):
            return False

        # Check included patterns
        if included_patterns:
            return self._url_matches_patterns(url, included_patterns, pattern_type)

        # If no included patterns specified, use base_url as default pattern
        # This allows crawling without explicitly setting patterns
        if pattern_type == "startswith":
            return url.startswith(task.base_url.rstrip("/"))
        else:
            # For regexp mode, if no patterns, default to base_url prefix match
            return url.startswith(task.base_url.rstrip("/"))

    def _add_doc_url(self, db: Session, url: str, link_text: str) -> DocURL:
        """Add discovered doc URL to database (if not exists)

        Special handling:
        1. Normalize URL by removing trailing slash
        2. Avoid duplicates
        3. Update link_text if existing record has empty text but new one doesn't

        Returns:
            The DocURL record (existing or newly created)
        """
        # Normalize URL by removing trailing slash
        normalized_url = url.rstrip("/")

        existing = (
            db.query(DocURL)
            .filter(DocURL.task_id == self.task_id, DocURL.url == normalized_url)
            .first()
        )

        if not existing:
            # New URL, add it
            doc_url = DocURL(
                task_id=self.task_id,
                url=normalized_url,
                link_text=link_text,
                discovered_at=datetime.now(timezone.utc),
            )
            db.add(doc_url)
            db.commit()
            return doc_url
        elif not existing.link_text and link_text:
            # Existing URL has empty link_text, but new one has text - update it
            existing.link_text = link_text
            db.commit()

        return existing

    def _fetch_page(self, url: str, timeout: int = 10):
        """Fetch page content"""
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _extract_links(self, html: str, base_url: str):
        """Extract all links from HTML

        Returns normalized URLs (fragment removed, trailing slash stripped)
        """
        soup = BeautifulSoup(html, "html.parser")
        links = []

        for link in soup.find_all("a", href=True):
            href = link.get("href")
            full_url = urljoin(base_url, href)
            # Remove fragment and trailing slash for normalization
            clean_url = full_url.split("#")[0].rstrip("/")
            link_text = link.get_text(strip=True)
            links.append((clean_url, link_text))

        return links

    def _process_link_detection(self, db: Session, doc_url: DocURL, task: Task):
        """
        Task 1: Link detection - extract links from the page

        Returns list of newly discovered DocURL records
        """
        if doc_url.link_detection_status == "done":
            return []

        # Update status to in_progress
        doc_url.link_detection_status = "in_progress"
        db.commit()

        try:
            # Fetch page HTML
            html = self._fetch_page(doc_url.url)
            if not html:
                doc_url.link_detection_status = "error"
                db.commit()
                return []

            # Extract links
            links = self._extract_links(html, doc_url.url)
            new_doc_urls = []

            for link_url, link_text in links:
                # Check if link should be processed
                if self._should_process_url(link_url, task):
                    # Add to doc_urls
                    discovered_doc_url = self._add_doc_url(db, link_url, link_text)
                    new_doc_urls.append(discovered_doc_url)

            # Mark as done
            doc_url.link_detection_status = "done"
            db.commit()

            print(f"[Link Detection] {doc_url.url} - found {len(new_doc_urls)} links")
            return new_doc_urls

        except Exception as e:
            print(f"[Link Detection Error] {doc_url.url}: {e}")
            doc_url.link_detection_status = "error"
            db.commit()
            return []

    def _process_content_crawl(self, db: Session, doc_url: DocURL):
        """
        Task 2: Content crawling - fetch markdown content using Jina API with caching
        """
        if doc_url.content_crawl_status == "done":
            return

        # Load task config
        task = self._load_task(db)
        config = json.loads(task.config) if task.config else {}

        # Check if content crawling is enabled
        if not config.get("crawl_content_enabled", True):
            return

        # Check if content already exists in cache
        cached_content = (
            db.query(DocContent).filter(DocContent.url == doc_url.url).first()
        )

        if cached_content:
            # Cache hit - reuse existing content
            doc_url.content_crawl_status = "done"
            db.commit()
            print(
                f"[Content Cache Hit] {doc_url.url} - {len(cached_content.markdown_content)} chars (cached at {cached_content.crawled_at})"
            )
            return

        # Cache miss - fetch from Jina API
        doc_url.content_crawl_status = "in_progress"
        db.commit()

        try:
            # Get CSS selectors from config
            selectors = config.get("content_css_selectors", [])

            markdown_content, error_message = fetch_markdown(
                doc_url.url, target_selectors=selectors if selectors else None
            )

            if markdown_content:
                # Save to cache
                doc_content = DocContent(
                    url=doc_url.url,
                    markdown_content=markdown_content,
                    crawled_at=datetime.now(timezone.utc),
                )
                db.add(doc_content)
                doc_url.content_crawl_status = "done"
                db.commit()
                print(f"[Content Crawl] {doc_url.url} - {len(markdown_content)} chars")
            else:
                # Save error to cache
                doc_content = DocContent(
                    url=doc_url.url,
                    markdown_content="",
                    error_message=error_message,
                    crawled_at=datetime.now(timezone.utc),
                )
                db.add(doc_content)
                doc_url.content_crawl_status = "error"
                db.commit()
                print(f"[Content Crawl Error] {doc_url.url}: {error_message}")

        except Exception as e:
            print(f"[Content Crawl Error] {doc_url.url}: {e}")
            doc_url.content_crawl_status = "error"
            db.commit()

    def _load_unfinished_doc_urls(self, db: Session):
        """
        Load all DocURL records that need processing (resume logic)

        Returns list of DocURL records where either:
        - link_detection_status != 'done'
        - content_crawl_status != 'done'
        """
        unfinished = (
            db.query(DocURL)
            .filter(
                DocURL.task_id == self.task_id,
                (
                    (DocURL.link_detection_status != "done")
                    | (DocURL.content_crawl_status != "done")
                ),
            )
            .all()
        )
        return unfinished

    def run(self):
        """Main crawling loop with dual tasks: link detection + content crawling"""
        db = SessionLocal()

        try:
            task = self._load_task(db)
            if not task:
                print(f"Task {self.task_id} not found")
                return

            print(f"Starting crawl for task {self.task_id}: {task.title}")

            # Initialize queue: load unfinished DocURLs from database (resume logic)
            unfinished_doc_urls = self._load_unfinished_doc_urls(db)

            if unfinished_doc_urls:
                print(f"Resuming: found {len(unfinished_doc_urls)} unfinished URLs")
                to_process = {doc_url.id: doc_url for doc_url in unfinished_doc_urls}
            else:
                # First run: create initial DocURL for base_url
                normalized_base_url = task.base_url.rstrip("/")
                initial_doc_url = self._add_doc_url(db, normalized_base_url, task.title)
                to_process = {initial_doc_url.id: initial_doc_url}
                print(f"Starting from base URL: {normalized_base_url}")

            processed_count = 0

            while to_process:
                # Check if we should continue
                if not self._check_status(db):
                    print(f"Task {self.task_id} stopped (status changed)")
                    break

                # Get next DocURL to process
                doc_url_id = next(iter(to_process))
                doc_url = to_process.pop(doc_url_id)

                # Refresh from database to get latest status
                db.expire(doc_url)
                db.refresh(doc_url)

                print(
                    f"\nProcessing [{self.task_id}] ({processed_count + 1}): {doc_url.url}"
                )

                # Task 1: Link Detection
                if doc_url.link_detection_status != "done":
                    newly_discovered = self._process_link_detection(db, doc_url, task)

                    # Add newly discovered URLs to processing queue
                    for new_doc_url in newly_discovered:
                        if new_doc_url.id not in to_process:
                            to_process[new_doc_url.id] = new_doc_url

                # Task 2: Content Crawling (only if enabled)
                if doc_url.content_crawl_status != "done":
                    self._process_content_crawl(db, doc_url)

                processed_count += 1

                # Small delay to be polite
                time.sleep(0.5)

            # Update task status to completed
            task = self._load_task(db)
            if task and task.status == "running":
                task.status = "completed"
                task.completed_at = datetime.now(timezone.utc)
                task.updated_at = datetime.now(timezone.utc)
                db.commit()

            print(f"\nTask {self.task_id} completed - processed {processed_count} URLs")

        except Exception as e:
            print(f"Error in crawler for task {self.task_id}: {e}")
            # Update task status to failed
            task = self._load_task(db)
            if task:
                task.status = "failed"
                task.completed_at = datetime.now(timezone.utc)
                task.updated_at = datetime.now(timezone.utc)
                db.commit()

        finally:
            db.close()

    def stop(self):
        """Signal the crawler to stop"""
        self.should_stop = True
