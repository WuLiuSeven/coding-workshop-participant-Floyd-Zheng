"""
Selenium end-to-end fixtures for the ACME frontend.

Configure with environment variables:
  E2E_BASE_URL     site to test   (default: http://localhost:5173, the Vite dev server)
  E2E_EMAIL        login email for an existing user
  E2E_PASSWORD     that user's password
  E2E_HEADLESS     "0" to watch the browser, anything else = headless (default)
  E2E_ALLOW_WRITES "1" to run tests that create data (e.g. reporting an incident)
"""
import os

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:5173").rstrip("/")
EMAIL = os.environ.get("E2E_EMAIL")
PASSWORD = os.environ.get("E2E_PASSWORD")
HEADLESS = os.environ.get("E2E_HEADLESS", "1") != "0"
ALLOW_WRITES = os.environ.get("E2E_ALLOW_WRITES") == "1"
TIMEOUT = 15


@pytest.fixture
def driver():
    options = webdriver.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1600,1000")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    drv = webdriver.Chrome(options=options)   # Selenium 4.6+ fetches chromedriver itself
    yield drv
    drv.quit()


class UI:
    """Small helper so tests read like user steps."""

    def __init__(self, driver):
        self.d = driver
        self.wait = WebDriverWait(driver, TIMEOUT)

    # --- finding things ---------------------------------------------------
    def visible(self, by, value):
        return self.wait.until(EC.visibility_of_element_located((by, value)))

    def clickable(self, by, value):
        return self.wait.until(EC.element_to_be_clickable((by, value)))

    def text_visible(self, text):
        return self.visible(By.XPATH, f"//*[contains(normalize-space(.), {xpath_literal(text)}) "
                                      f"and not(.//*[contains(normalize-space(.), {xpath_literal(text)})])]")

    def button(self, text):
        return self.clickable(By.XPATH, f"//button[normalize-space(.)={xpath_literal(text)}]")

    def first_present(self, *locators, timeout=TIMEOUT):
        """Return the first element matching any of the locators (handles differing markup)."""
        def _find(d):
            for by, value in locators:
                found = d.find_elements(by, value)
                if found and found[0].is_displayed():
                    return found[0]
            return False
        return WebDriverWait(self.d, timeout).until(_find)

    def is_present(self, by, value, timeout=3):
        try:
            WebDriverWait(self.d, timeout).until(EC.presence_of_element_located((by, value)))
            return True
        except TimeoutException:
            return False

    # --- flows --------------------------------------------------------------
    def open(self, path=""):
        self.d.get(f"{BASE_URL}/{path.lstrip('/')}")

    def login(self, email, password):
        self.open()
        email_input = self.first_present(
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.CSS_SELECTOR, "input[name='email']"),
            (By.CSS_SELECTOR, "input[name='username']"),
            (By.CSS_SELECTOR, "input[autocomplete='email'], input[autocomplete='username']"),
            (By.CSS_SELECTOR, "form input:not([type='password']):not([type='hidden']):not([type='checkbox'])"),
            (By.CSS_SELECTOR, "input:not([type='password']):not([type='hidden']):not([type='checkbox'])"),
        )
        password_input = self.first_present((By.CSS_SELECTOR, "input[type='password']"))
        email_input.clear()
        email_input.send_keys(email)
        password_input.clear()
        password_input.send_keys(password)
        self.first_present(
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.XPATH, "//button[contains(translate(., 'LOGIN', 'login'), 'log')]"),
        ).click()


def xpath_literal(s):
    """Quote a string safely for XPath (handles apostrophes)."""
    if "'" not in s:
        return f"'{s}'"
    if '"' not in s:
        return f'"{s}"'
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in s.split("'")) + ")"


@pytest.fixture
def ui(driver):
    return UI(driver)


@pytest.fixture
def logged_in(ui):
    if not (EMAIL and PASSWORD):
        pytest.skip("set E2E_EMAIL and E2E_PASSWORD to run logged-in tests")
    ui.login(EMAIL, PASSWORD)
    ui.button("Log Out")          # proves the dashboard rendered
    return ui
