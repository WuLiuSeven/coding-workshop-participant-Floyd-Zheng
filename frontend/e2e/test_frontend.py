"""
Selenium end-to-end tests for the ACME frontend.

    pip install -r e2e/requirements-e2e.txt
    E2E_EMAIL=you@acme.inc E2E_PASSWORD=... python -m pytest e2e -v
"""
import time

import pytest
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from conftest import ALLOW_WRITES, xpath_literal


def _tab(ui, prefix):
    return ui.clickable(By.XPATH, f"//button[@role='tab' and starts-with(normalize-space(.), {xpath_literal(prefix)})]")


def _hover_tooltip(ui, element):
    ActionChains(ui.d).move_to_element(element).perform()
    return ui.visible(By.CSS_SELECTOR, "[role='tooltip']").text


# --------------------------------------------------------------------------- #
# Login / logout
# --------------------------------------------------------------------------- #
def test_login_page_loads(ui):
    ui.open()
    assert ui.is_present(By.CSS_SELECTOR, "input[type='password']", timeout=15)


def test_bad_credentials_stay_on_login(ui):
    ui.login("nobody@acme.inc", "definitely-wrong-password")
    time.sleep(1.5)  # let the API answer
    assert ui.is_present(By.CSS_SELECTOR, "input[type='password']")
    assert not ui.is_present(By.XPATH, "//button[normalize-space(.)='Log Out']", timeout=2)


def test_login_shows_dashboard(logged_in):
    assert logged_in.is_present(By.XPATH, "//button[@role='tab' and starts-with(normalize-space(.), 'Seats (')]")


def test_logout_returns_to_login(logged_in):
    logged_in.button("Log Out").click()
    assert logged_in.is_present(By.CSS_SELECTOR, "input[type='password']", timeout=10)


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
def test_acme_logo_is_a_home_button(logged_in):
    acme = logged_in.clickable(By.CSS_SELECTOR, "[aria-label^='ACME home']")
    assert "Locations & Incidents" in _hover_tooltip(logged_in, acme)

    _tab(logged_in, "Facilities (").click()
    acme.click()
    # still on the Locations & Incidents page
    assert logged_in.is_present(By.XPATH, "//*[normalize-space(.)='Incidents by status']")


# --------------------------------------------------------------------------- #
# Analytics panel
# --------------------------------------------------------------------------- #
def test_analytics_panel_is_visible(logged_in):
    for title in ("Incidents by status", "Time to acknowledge", "Time to complete"):
        logged_in.text_visible(title)
    for slice_label in ("Reported", "In progress", "Completed"):
        assert logged_in.is_present(By.XPATH, f"//p[normalize-space(.)={xpath_literal(slice_label)}]")
    assert logged_in.is_present(By.CSS_SELECTOR, "svg[aria-label='Incidents by status']")


@pytest.mark.parametrize("slice_label", ["Reported", "In progress", "Completed"])
def test_clicking_pie_legend_filters_incidents(logged_in, slice_label):
    logged_in.clickable(By.XPATH, f"//p[normalize-space(.)={xpath_literal(slice_label)}]").click()

    incidents_tab = _tab(logged_in, "Incidents (")
    logged_in.wait.until(lambda d: incidents_tab.get_attribute("aria-selected") == "true")
    chip = logged_in.text_visible(f"Status: {slice_label}")

    # every row shown is in the chosen state (Progress column)
    cells = logged_in.d.find_elements(By.CSS_SELECTOR, "[role='gridcell'][data-field='state']")
    assert all(c.text == slice_label for c in cells)

    # removing the chip clears the filter
    chip.find_element(By.XPATH, "./ancestor::div[contains(@class,'MuiChip-root')]//*[local-name()='svg']").click()
    assert not logged_in.is_present(By.XPATH, f"//*[normalize-space(.)='Status: {slice_label}']", timeout=2)


# --------------------------------------------------------------------------- #
# Seat actions: icons + tooltips
# --------------------------------------------------------------------------- #
def test_seat_action_tooltips(logged_in):
    report = logged_in.clickable(By.CSS_SELECTOR, "button[aria-label='Report incident']")
    assert _hover_tooltip(logged_in, report) == "Report a problem with this seat"

    view = logged_in.d.find_element(By.CSS_SELECTOR, "button[aria-label='View incidents']")
    ActionChains(logged_in.d).move_to_element(view).perform()
    tip = logged_in.wait.until(
        lambda d: next((t.text for t in d.find_elements(By.CSS_SELECTOR, "[role='tooltip']")
                        if "for this seat" in t.text and not t.text.startswith("Report")), False)
    )
    # "View N incidents for this seat" or "No incidents reported for this seat"
    assert tip.startswith(("View", "No incidents"))


def test_report_dialog_opens_and_cancels(logged_in):
    logged_in.clickable(By.CSS_SELECTOR, "button[aria-label='Report incident']").click()
    dialog = logged_in.visible(By.CSS_SELECTOR, "[role='dialog']")
    assert "Report Incident" in dialog.text

    report_btn = dialog.find_element(By.XPATH, ".//button[normalize-space(.)='Report']")
    assert not report_btn.is_enabled()   # category + priority not chosen yet

    dialog.find_element(By.XPATH, ".//button[normalize-space(.)='Cancel']").click()
    logged_in.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "[role='dialog']")))


# --------------------------------------------------------------------------- #
# Writes data: only runs with E2E_ALLOW_WRITES=1
# --------------------------------------------------------------------------- #
def _choose(ui, dialog, label, option):
    dialog.find_element(
        By.XPATH,
        f".//label[contains(normalize-space(.), {xpath_literal(label)})]"
        "/following-sibling::div//*[@role='combobox' or @aria-haspopup='listbox']",
    ).click()
    ui.clickable(By.XPATH, f"//li[@role='option' and normalize-space(.)={xpath_literal(option)}]").click()


@pytest.mark.skipif(not ALLOW_WRITES, reason="set E2E_ALLOW_WRITES=1 to create real incidents")
def test_report_incident_end_to_end(logged_in):
    mine_tab = _tab(logged_in, "My Incidents (")
    before = int(mine_tab.text.split("(")[1].rstrip(")"))

    logged_in.clickable(By.CSS_SELECTOR, "button[aria-label='Report incident']").click()
    dialog = logged_in.visible(By.CSS_SELECTOR, "[role='dialog']")
    _choose(logged_in, dialog, "Category", "Hardware")
    _choose(logged_in, dialog, "Priority", "Low")
    dialog.find_element(By.TAG_NAME, "textarea").send_keys("Selenium e2e test, safe to delete")
    dialog.find_element(By.XPATH, ".//button[normalize-space(.)='Report']").click()

    logged_in.text_visible("Incident reported for seat")
    logged_in.wait.until(
        lambda d: int(_tab(logged_in, "My Incidents (").text.split("(")[1].rstrip(")")) == before + 1
    )
