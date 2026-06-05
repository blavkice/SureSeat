"""Headless-Chrome confirmation of reservation links.

The Affluences confirmation email links to a page with a "confirm" button.
:class:`Validator` opens that page, clicks the button (matching localized
labels from :data:`sureseat.i18n.KEYWORDS`) and reports whether the page then
shows a success/already-confirmed message.
"""

import random
import time
from dataclasses import dataclass

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .. import chrome, config
from ..i18n import KEYWORDS

_LOWER = "translate(%s, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')"


@dataclass
class ValidationResult:
    """Outcome of validating a single reservation link."""
    index: int
    success: bool
    error: str = ""


def _button_selectors(button_keywords):
    """Build XPath selectors that match a confirm button in any language."""
    href = " or ".join(f"contains(@href, '{kw}')" for kw in button_keywords)
    text = " or ".join(
        f"contains({_LOWER % 'text()'}, '{kw}')" for kw in button_keywords
    )
    value = " or ".join(
        f"contains({_LOWER % '@value'}, '{kw}')" for kw in button_keywords
    )
    return [
        f"//a[{href}]",
        f"//button[{text}]",
        f"//a[{text}]",
        f"//input[@type='submit' and ({value})]",
        f"//*[@role='button' and ({text})]",
    ]


class Validator:
    """Validates confirmation links using short-lived headless Chrome drivers."""

    def __init__(self, driver_path, timeout=None, max_retries=2):
        self.driver_path = driver_path
        self.timeout = timeout or config.SELENIUM_TIMEOUT
        self.max_retries = max_retries

    def _new_driver(self):
        options = chrome.build_options(random.choice(config.USER_AGENTS))
        service = Service(executable_path=self.driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(self.timeout)
        driver.set_script_timeout(self.timeout)
        return driver

    def validate(self, link, index=0):
        """Open ``link`` and confirm it. Returns a :class:`ValidationResult`."""
        button_kw = KEYWORDS.get("button", ["confirm", "conferma"])
        success_kw = KEYWORDS.get("success", ["success", "confirmed"])
        already_kw = KEYWORDS.get("already", ["already confirmed"])

        for attempt in range(self.max_retries + 1):
            driver = None
            try:
                driver = self._new_driver()
                driver.get(link)
                wait = WebDriverWait(driver, self.timeout)

                btn = self._find_button(driver, wait, _button_selectors(button_kw))
                if btn:
                    btn.click()
                    time.sleep(1.5)
                    page = driver.page_source.lower()
                    if any(kw in page for kw in success_kw):
                        return ValidationResult(index, True)
                    return ValidationResult(index, False,
                                            "No success confirmation after click")

                page = driver.page_source.lower()
                if any(kw in page for kw in already_kw + success_kw):
                    return ValidationResult(index, True)
                return ValidationResult(index, False, "Confirm button not found")

            except Exception as exc:
                msg = str(exc).lower()
                retriable = "chrome" in msg or "connection" in msg
                if attempt < self.max_retries and retriable:
                    self._quit(driver)
                    time.sleep(0.3)
                    continue
                # Last-chance: maybe the page already shows confirmation.
                page = self._safe_page_source(driver)
                if page and any(kw in page for kw in already_kw + success_kw):
                    return ValidationResult(index, True)
                return ValidationResult(index, False, str(exc)[:100])
            finally:
                self._quit(driver)

        return ValidationResult(index, False, "Exhausted retries")

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _find_button(driver, wait, selectors):
        for selector in selectors:
            try:
                wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                el = driver.find_element(By.XPATH, selector)
                driver.execute_script("arguments[0].scrollIntoView(true);", el)
                return wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
            except Exception:
                continue
        return None

    @staticmethod
    def _safe_page_source(driver):
        try:
            return driver.page_source.lower() if driver else None
        except Exception:
            return None

    @staticmethod
    def _quit(driver):
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
