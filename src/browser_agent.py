"""Browser Automation - Web browsing agent for CrackedCode.

Features:
- Navigate to URLs
- Click elements
- Fill forms
- Take screenshots
- Extract text/content
- Scroll pages

Uses Playwright for browser automation.
"""

import base64
import io
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = get_logger("BrowserAgent")


@dataclass
class BrowserActionResult:
    """Result of a browser action."""
    success: bool
    url: str = ""
    title: str = ""
    content: str = ""
    screenshot: bytes = b""
    error: str = ""


class BrowserAgent:
    """Agent for browser automation using Playwright."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._initialized = False
        
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available - browser automation disabled")
    
    def _init(self) -> bool:
        """Initialize browser if not already done."""
        if self._initialized:
            return True
        if not PLAYWRIGHT_AVAILABLE:
            return False
        
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._page = self._browser.new_page(viewport={"width": 1280, "height": 720})
            self._initialized = True
            logger.info("Browser agent initialized")
            return True
        except Exception as e:
            logger.error(f"Browser init failed: {e}")
            return False
    
    def navigate(self, url: str, wait_until: str = "networkidle") -> BrowserActionResult:
        """Navigate to a URL."""
        if not self._init():
            return BrowserActionResult(success=False, error="Browser not available")
        
        try:
            self._page.goto(url, wait_until=wait_until, timeout=30000)
            return BrowserActionResult(
                success=True,
                url=self._page.url,
                title=self._page.title(),
            )
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return BrowserActionResult(success=False, error=str(e))
    
    def click(self, selector: str) -> BrowserActionResult:
        """Click an element by CSS selector."""
        if not self._init():
            return BrowserActionResult(success=False, error="Browser not available")
        
        try:
            self._page.click(selector, timeout=10000)
            return BrowserActionResult(
                success=True,
                url=self._page.url,
                title=self._page.title(),
            )
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return BrowserActionResult(success=False, error=str(e))
    
    def fill(self, selector: str, text: str) -> BrowserActionResult:
        """Fill a form field."""
        if not self._init():
            return BrowserActionResult(success=False, error="Browser not available")
        
        try:
            self._page.fill(selector, text, timeout=10000)
            return BrowserActionResult(
                success=True,
                url=self._page.url,
                title=self._page.title(),
            )
        except Exception as e:
            logger.error(f"Fill failed: {e}")
            return BrowserActionResult(success=False, error=str(e))
    
    def screenshot(self, full_page: bool = False) -> BrowserActionResult:
        """Take a screenshot of the current page."""
        if not self._init():
            return BrowserActionResult(success=False, error="Browser not available")
        
        try:
            screenshot_bytes = self._page.screenshot(full_page=full_page, type="png")
            return BrowserActionResult(
                success=True,
                url=self._page.url,
                title=self._page.title(),
                screenshot=screenshot_bytes,
            )
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return BrowserActionResult(success=False, error=str(e))
    
    def get_text(self, selector: str = None) -> BrowserActionResult:
        """Extract text content from page or element."""
        if not self._init():
            return BrowserActionResult(success=False, error="Browser not available")
        
        try:
            if selector:
                content = self._page.text_content(selector, timeout=10000)
            else:
                content = self._page.content()
            return BrowserActionResult(
                success=True,
                url=self._page.url,
                title=self._page.title(),
                content=content or "",
            )
        except Exception as e:
            logger.error(f"Get text failed: {e}")
            return BrowserActionResult(success=False, error=str(e))
    
    def scroll(self, direction: str = "down", amount: int = 500) -> BrowserActionResult:
        """Scroll the page."""
        if not self._init():
            return BrowserActionResult(success=False, error="Browser not available")
        
        try:
            if direction == "down":
                self._page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                self._page.evaluate(f"window.scrollBy(0, -{amount})")
            elif direction == "bottom":
                self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "top":
                self._page.evaluate("window.scrollTo(0, 0)")
            
            return BrowserActionResult(
                success=True,
                url=self._page.url,
                title=self._page.title(),
            )
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return BrowserActionResult(success=False, error=str(e))
    
    def close(self):
        """Close browser and cleanup."""
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
            self._initialized = False
            logger.info("Browser agent closed")
        except Exception as e:
            logger.error(f"Browser close error: {e}")


def get_browser_agent(headless: bool = True) -> BrowserAgent:
    """Get a BrowserAgent instance."""
    return BrowserAgent(headless=headless)
