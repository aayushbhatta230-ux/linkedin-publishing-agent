"""
URL intake and metadata extraction service.
Specialized parsers for GitHub repositories and arbitrary public web demo pages.
Zero third-party scraper dependencies (built-in HTML parser + requests).
"""
import html
import logging
import re
from html.parser import HTMLParser
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger("url_intake")


class SimpleMetadataParser(HTMLParser):
    """Lightweight HTML parser to extract page title, meta description, and first heading."""

    def __init__(self):
        super().__init__()
        self.in_title = False
        self.in_h1 = False
        self.title = ""
        self.description = ""
        self.h1 = ""
        self.body_text_chunks = []
        self._current_tag = ""

    def handle_starttag(self, tag: str, attrs: list):
        self._current_tag = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag.lower() == "title":
            self.in_title = True
        elif tag.lower() == "h1":
            self.in_h1 = True
        elif tag.lower() == "meta":
            name = attr_dict.get("name", "").lower()
            prop = attr_dict.get("property", "").lower()
            content = attr_dict.get("content", "").strip()

            if name == "description" or prop in ("og:description", "twitter:description"):
                if not self.description:
                    self.description = content

    def handle_endtag(self, tag: str):
        if tag.lower() == "title":
            self.in_title = False
        elif tag.lower() == "h1":
            self.in_h1 = False

    def handle_data(self, data: str):
        cleaned = data.strip()
        if not cleaned:
            return

        if self.in_title:
            self.title += f" {cleaned}"
        elif self.in_h1 and not self.h1:
            self.h1 = cleaned
        elif self._current_tag in ("p", "div", "section", "article", "li"):
            if len(" ".join(self.body_text_chunks)) < 1500:
                self.body_text_chunks.append(cleaned)


class URLIntakeService:
    """Provides resilient inspection of GitHub repos and public web demo links."""

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 LocalProjectIntake/1.0",
            "Accept": "text/html,application/xhtml+xml,application/json",
        })

    def is_github_url(self, url: str) -> bool:
        """Determines if the URL points to a GitHub repository."""
        parsed = urlparse(url.strip())
        return "github.com" in (parsed.netloc or "").lower()

    def parse_github_repo(self, url: str) -> Optional[Tuple[str, str]]:
        """Extracts owner and repo name from GitHub URL."""
        parsed = urlparse(url.strip())
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "")
        return None

    def fetch_github_info(self, url: str) -> Dict[str, Any]:
        """
        Fetches repository details using GitHub's public API and raw README.
        Works without authentication (up to standard IP rate limits).
        """
        repo_info = self.parse_github_repo(url)
        if not repo_info:
            return {"success": False, "error": "Invalid GitHub repository URL format."}

        owner, repo = repo_info
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        result: Dict[str, Any] = {
            "success": True,
            "type": "github",
            "url": url,
            "owner": owner,
            "repo": repo,
            "title": f"{owner}/{repo}",
            "description": "",
            "language": "",
            "topics": [],
            "readme_excerpt": "",
            "formatted_summary": "",
        }

        try:
            resp = self.session.get(api_url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                result["description"] = data.get("description") or ""
                result["language"] = data.get("language") or ""
                result["topics"] = data.get("topics", [])
                result["stars"] = data.get("stargazers_count", 0)
            elif resp.status_code == 404:
                return {"success": False, "error": f"GitHub repository '{owner}/{repo}' not found or is private."}
            else:
                logger.warning("GitHub API returned HTTP %s for %s", resp.status_code, api_url)
        except requests.RequestException as e:
            logger.warning("GitHub API request failed: %s", e)

        # Attempt to fetch README excerpt
        for branch in ("main", "master"):
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
            try:
                readme_resp = self.session.get(raw_url, timeout=self.timeout)
                if readme_resp.status_code == 200:
                    raw_text = readme_resp.text
                    # Strip markdown links and headers for cleaner LLM context
                    cleaned_readme = re.sub(r"!\[.*?\]\(.*?\)", "", raw_text)
                    cleaned_readme = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", cleaned_readme)
                    # Excerpt first 1500 chars
                    result["readme_excerpt"] = cleaned_readme[:1500].strip()
                    break
            except requests.RequestException:
                pass

        # Build combined summary
        summary_lines = [
            f"GitHub Project: {owner}/{repo}",
            f"Primary Language: {result['language']}" if result['language'] else "",
            f"Description: {result['description']}" if result['description'] else "",
            f"Topics: {', '.join(result['topics'])}" if result['topics'] else "",
            f"\nREADME Overview:\n{result['readme_excerpt']}" if result['readme_excerpt'] else "",
        ]
        result["formatted_summary"] = "\n".join(line for line in summary_lines if line).strip()
        return result

    def fetch_webpage_info(self, url: str) -> Dict[str, Any]:
        """
        Fetches public demo or documentation webpage and extracts metadata.
        """
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            return {"success": False, "error": f"Failed to connect to {url}: {e}"}

        if resp.status_code != 200:
            return {"success": False, "error": f"Webpage returned HTTP {resp.status_code}"}

        parser = SimpleMetadataParser()
        try:
            parser.feed(resp.text[:100000])  # limit parse size
        except Exception as e:
            logger.warning("HTML parsing warning: %s", e)

        title = html.unescape(parser.title.strip()) or parser.h1.strip() or url
        description = html.unescape(parser.description.strip())
        content_preview = " ".join(parser.body_text_chunks)[:1000].strip()

        formatted = [
            f"Page Title: {title}",
            f"Description: {description}" if description else "",
            f"Heading: {parser.h1.strip()}" if parser.h1 and parser.h1 != title else "",
            f"Page Summary: {content_preview}" if content_preview else "",
        ]

        return {
            "success": True,
            "type": "webpage",
            "url": url,
            "title": title,
            "description": description,
            "formatted_summary": "\n".join(f for f in formatted if f).strip(),
        }

    def inspect_url(self, url: str) -> Dict[str, Any]:
        """Auto-detects URL type and returns extracted summary context."""
        if not url or not url.strip():
            return {"success": False, "error": "URL cannot be empty."}

        clean_url = url.strip()
        if self.is_github_url(clean_url):
            return self.fetch_github_info(clean_url)
        return self.fetch_webpage_info(clean_url)


url_intake = URLIntakeService()
