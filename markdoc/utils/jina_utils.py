"""
Jina AI API utilities for fetching documentation content as markdown.
"""

import requests

from markdoc.config import CONFIG


def fetch_markdown(
    url: str, timeout: int = 30, target_selectors: list[str] | None = None
) -> tuple[str | None, str | None]:
    """
    Fetch markdown content from a URL using Jina AI Reader API.

    Args:
        url: The URL to fetch content from
        timeout: Request timeout in seconds
        target_selectors: Optional list of CSS selectors to target specific content

    Returns:
        Tuple of (markdown_content, error_message)
        - If successful: (markdown_content, None)
        - If failed: (None, error_message)
    """
    api_key = CONFIG.get("jina.api_key")
    if not api_key:
        return None, "Jina API key not configured"

    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Engine": "browser",
        "X-Return-Format": "markdown",
    }

    # Add target selector header if provided
    if target_selectors:
        headers["X-Target-Selector"] = ", ".join(target_selectors)

    try:
        response = requests.get(jina_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text, None
    except requests.exceptions.HTTPError as e:
        # Handle 422 status code (selector not found) - fallback to no selector
        if e.response.status_code == 422 and target_selectors:
            print(
                f"[Jina Fallback] Selectors {target_selectors} not found for {url}, retrying without selectors"
            )
            return fetch_markdown(url, timeout, target_selectors=None)
        return None, f"Request failed: {str(e)}"
    except requests.exceptions.Timeout:
        return None, f"Request timeout after {timeout}s"
    except requests.exceptions.RequestException as e:
        return None, f"Request failed: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"


__all__ = [
    "fetch_markdown",
]
