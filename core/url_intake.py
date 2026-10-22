"""
URL intake and metadata extraction service.
Specialized parsers for GitHub repositories and arbitrary public web demo pages.
Auto-recognizes repositories by name/title across known user handles (e.g. aayushbhatta230-ux).
Zero third-party scraper dependencies (built-in HTML parser + requests).
"""
import html
import logging
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger("url_intake")

KNOWN_GITHUB_HANDLES = ["aayushbhatta230-ux", "aayushbhatta"]


class SimpleMetadataParser(HTMLParser):
    """Lightweight HTML parser to extract page title, meta description, and headings."""

    def __init__(self):
        super().__init__()
        self.in_title = False
        self.in_h1 = False
        self.title = ""
        self.description = ""
        self.h1 = ""
        self.body_text_chunks: List[str] = []
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
        elif self._current_tag in ("p", "div", "section", "article", "li", "h2", "h3"):
            if sum(len(c) for c in self.body_text_chunks) < 5000:
                self.body_text_chunks.append(cleaned)


class URLIntakeService:
    """Provides resilient inspection of GitHub repos and public web demo links."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 LocalProjectIntake/1.0",
            "Accept": "text/html,application/xhtml+xml,application/json",
            "Connection": "close",
        })

    def is_github_url(self, url: str) -> bool:
        """Determines if the URL points to a GitHub repository."""
        parsed = urlparse(url.strip())
        return "github.com" in (parsed.netloc or "").lower()

    def parse_github_repo(self, url: str) -> Optional[Tuple[str, str]]:
        """Extracts owner and repo name from GitHub URL or owner/repo format."""
        clean = url.strip()
        if not clean.startswith("http://") and not clean.startswith("https://"):
            if "/" in clean and not clean.startswith("/"):
                parts = clean.split("/")
                if len(parts) >= 2:
                    return parts[0].strip(), parts[1].replace(".git", "").strip()
            clean = f"https://{clean}"

        parsed = urlparse(clean)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "")
        return None

    def resolve_repo_by_name(self, query: str) -> Optional[str]:
        """
        Auto-recognizes a repository name or query across known user GitHub accounts.
        Example: 'city-ai-aayushifty' or 'AI OPERATED CITY' -> returns GitHub repo URL.
        """
        clean_query = query.strip().lower()
        if not clean_query:
            return None

        # Direct normalization
        slug = re.sub(r"[^a-z0-9]+", "-", clean_query).strip("-")

        for handle in KNOWN_GITHUB_HANDLES:
            try:
                # Query user repos via public GitHub API
                api_url = f"https://api.github.com/users/{handle}/repos?per_page=50&sort=updated"
                resp = self.session.get(api_url, timeout=self.timeout)
                if resp.status_code == 200:
                    repos = resp.json()
                    for r in repos:
                        r_name = r.get("name", "").lower()
                        r_desc = (r.get("description") or "").lower()

                        # Exact or slug match
                        if r_name == slug or slug in r_name or r_name in slug:
                            return r.get("html_url")

                        # Keyword match
                        words = [w for w in clean_query.split() if len(w) > 2]
                        if words and all(w in r_name or w in r_desc for w in words):
                            return r.get("html_url")
            except Exception as e:
                logger.warning("Error resolving repo for %s: %s", handle, e)

        return None

    def fetch_github_info(self, url: str) -> Dict[str, Any]:
        """
        Fetches repository details using GitHub's public API and FULL raw README.
        Captures full technical context without tiny truncations.
        """
        repo_info = self.parse_github_repo(url)
        if not repo_info:
            return {"success": False, "error": "Invalid GitHub repository URL format."}

        owner, repo = repo_info
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        result: Dict[str, Any] = {
            "success": True,
            "type": "github",
            "url": f"https://github.com/{owner}/{repo}",
            "owner": owner,
            "repo": repo,
            "title": f"{owner}/{repo}",
            "description": "",
            "language": "",
            "topics": [],
            "readme_full": "",
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
        except requests.RequestException as e:
            logger.warning("GitHub API request failed: %s", e)

        # Attempt to fetch full README
        for branch in ("main", "master"):
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
            try:
                readme_resp = self.session.get(raw_url, timeout=self.timeout)
                if readme_resp.status_code == 200:
                    raw_text = readme_resp.text
                    # Clean badges and image markdown while preserving headings and text
                    cleaned = re.sub(r"!\[.*?\]\(.*?\)", "", raw_text)
                    cleaned = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", cleaned)
                    # Feed up to 8,000 characters to ensure full architecture & details are captured
                    result["readme_full"] = cleaned[:8000].strip()
                    break
            except requests.RequestException:
                pass

        # Build comprehensive summary
        summary_lines = [
            f"GitHub Repository: {owner}/{repo}",
            f"Primary Language: {result['language']}" if result['language'] else "",
            f"Description: {result['description']}" if result['description'] else "",
            f"Topics: {', '.join(result['topics'])}" if result['topics'] else "",
            f"\nFull Technical README & Architecture:\n{result['readme_full']}" if result['readme_full'] else "",
        ]
        result["formatted_summary"] = "\n".join(line for line in summary_lines if line).strip()
        return result

    def fetch_webpage_info(self, url: str) -> Dict[str, Any]:
        """Fetches public demo or documentation webpage and extracts rich metadata."""
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
            parser.feed(resp.text[:200000])
        except Exception as e:
            logger.warning("HTML parsing warning: %s", e)

        title = html.unescape(parser.title.strip()) or parser.h1.strip() or url
        description = html.unescape(parser.description.strip())
        content_preview = " ".join(parser.body_text_chunks)[:4000].strip()

        formatted = [
            f"Page Title: {title}",
            f"Description: {description}" if description else "",
            f"Heading: {parser.h1.strip()}" if parser.h1 and parser.h1 != title else "",
            f"Full Page Content:\n{content_preview}" if content_preview else "",
        ]

        return {
            "success": True,
            "type": "webpage",
            "url": url,
            "title": title,
            "description": description,
            "formatted_summary": "\n".join(f for f in formatted if f).strip(),
        }

    def inspect_url(self, input_text: str) -> Dict[str, Any]:
        """
        Auto-recognizes URL or repository name and returns extracted full summary context.
        """
        if not input_text or not input_text.strip():
            return {"success": False, "error": "Input cannot be empty."}

        clean = input_text.strip()

        # If it's a GitHub URL or owner/repo format
        if self.is_github_url(clean) or ("/" in clean and not clean.startswith("http")):
            return self.fetch_github_info(clean)

        # If it starts with standard http/https
        if clean.startswith("http://") or clean.startswith("https://"):
            return self.fetch_webpage_info(clean)

        # Auto-resolve repository by title/name
        resolved_url = self.resolve_repo_by_name(clean)
        if resolved_url:
            logger.info("Auto-recognized '%s' as repository %s", clean, resolved_url)
            return self.fetch_github_info(resolved_url)

        return self.fetch_webpage_info(clean)


url_intake = URLIntakeService()
