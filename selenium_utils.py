from __future__ import annotations

import time

from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


Locator = tuple[str, str]

SET_REACTIVE_VALUE_SCRIPT = """
const element = arguments[0];
const value = arguments[1];
Object.getOwnPropertyDescriptor(
    Object.getPrototypeOf(element),
    'value'
).set.call(element, value);
element.dispatchEvent(new InputEvent('input', {
    bubbles: true,
    data: value,
    inputType: 'insertText',
}));
element.dispatchEvent(new Event('change', { bubbles: true }));
"""


def error_summary(error: Exception) -> str:
    lines = [line.strip() for line in str(error).splitlines() if line.strip()]
    return lines[0] if lines else type(error).__name__


def build_driver(headless: bool, keep_open: bool) -> webdriver.Chrome:
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
    if keep_open and not headless:
        options.add_experimental_option("detach", True)
    return webdriver.Chrome(options=options)


def wait_until_loaded(driver: webdriver.Chrome, timeout: int) -> None:
    wait = WebDriverWait(driver, timeout)
    wait.until(
        lambda browser: browser.execute_script("return document.readyState")
        == "complete"
    )
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))


def click_element(driver: webdriver.Chrome, element: WebElement) -> None:
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)


def click_when_present(
    driver: webdriver.Chrome,
    locator: Locator,
    element_name: str,
    timeout: int = 3,
) -> bool:
    print(f"Waiting for '{element_name}'...")
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        click_element(driver, element)
        print(f"Clicked '{element_name}'.")
        time.sleep(1)
        return True
    except Exception as error:
        print(f"Could not click '{element_name}': {error_summary(error)}")
        return False


def replace_with_keyboard(
    driver: webdriver.Chrome, element: WebElement, value: str
) -> None:
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});", element
    )
    try:
        element.click()
    except ElementClickInterceptedException:
        # Xiaomi's floating label can cover the input even though it is ready.
        driver.execute_script("arguments[0].focus();", element)
    element.send_keys(Keys.CONTROL, "a")
    element.send_keys(Keys.BACKSPACE)
    element.send_keys(value)


def set_reactive_value(
    driver: webdriver.Chrome,
    element: WebElement,
    value: str,
    timeout: int,
) -> None:
    driver.execute_script(SET_REACTIVE_VALUE_SCRIPT, element, value)
    WebDriverWait(driver, timeout).until(
        lambda browser: element.get_attribute("value") == value
    )
