from __future__ import annotations

import re
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from selenium_utils import (
    Locator,
    click_element,
    click_when_present,
    error_summary,
    replace_with_keyboard,
    set_reactive_value,
    wait_until_loaded,
)


TEMPMAIL_URL = "https://tempmail.id.vn/en"
CUSTOM_MAIL_INPUT: Locator = (
    By.XPATH,
    "//input[@*[name()='wire:model']='customMail' or @placeholder='Input custom mail']",
)
CREATE_MAIL_BUTTON: Locator = (By.XPATH, "//button[normalize-space(.)='Create']")
MAILBOX_ADDRESS: Locator = (By.XPATH, "//button[contains(., '@')]")
INBOX_MESSAGE_LINKS: Locator = (
    By.CSS_SELECTOR, "tr.fi-clickable a[href*='/message/']"
)
REFRESH_INBOX_BUTTON: Locator = (By.XPATH, "//button[normalize-space(.)='Refresh']")
MESSAGE_FRAME: Locator = (By.CSS_SELECTOR, "iframe[srcdoc]")

XIAOMI_OTP_PATTERN = re.compile(
    r"verification\s+code\s*(?:is)?\s*:\s*([0-9]{4,8})", re.IGNORECASE
)
CONTEXTUAL_OTP_PATTERN = re.compile(
    r"(?:otp|one[- ]?time(?:\s+pass(?:word|code))?|verification|verify|security)"
    r"[^\d]{0,80}([0-9]{4,8})",
    re.IGNORECASE,
)
GENERIC_OTP_PATTERN = re.compile(r"(?<!\d)([0-9]{4,8})(?!\d)")


def fill_custom_email(
    driver: webdriver.Chrome, username: str, timeout: int = 5
) -> bool:
    print("Waiting for custom mail input...")
    try:
        input_element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(CUSTOM_MAIL_INPUT)
        )
        replace_with_keyboard(driver, input_element, username)
        set_reactive_value(driver, input_element, username, timeout)
        print(f"Custom mailbox name entered: {username}")
        time.sleep(1)
        return True
    except Exception as error:
        print(f"Could not enter the custom mailbox name: {error_summary(error)}")
        return False


def extract_otp(text: str) -> str | None:
    for pattern in (XIAOMI_OTP_PATTERN, CONTEXTUAL_OTP_PATTERN, GENERIC_OTP_PATTERN):
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def read_current_email_text(driver: webdriver.Chrome) -> str:
    text_parts = [driver.find_element(By.TAG_NAME, "body").text]
    for frame in driver.find_elements(*MESSAGE_FRAME):
        try:
            driver.switch_to.frame(frame)
            text_parts.append(driver.find_element(By.TAG_NAME, "body").text)
        except Exception:
            pass
        finally:
            driver.switch_to.default_content()
    return "\n".join(text_parts)


def refresh_inbox(driver: webdriver.Chrome) -> None:
    refresh_buttons = driver.find_elements(*REFRESH_INBOX_BUTTON)
    if refresh_buttons:
        click_element(driver, refresh_buttons[0])


def first_message_url(driver: webdriver.Chrome) -> str | None:
    message_links = driver.find_elements(*INBOX_MESSAGE_LINKS)
    return message_links[0].get_attribute("href") if message_links else None


def wait_for_first_email_otp(
    driver: webdriver.Chrome, timeout: int
) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message_url = first_message_url(driver)
        if not message_url:
            refresh_inbox(driver)
            time.sleep(2)
            continue

        print("First email received. Opening it...")
        driver.get(message_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located(MESSAGE_FRAME))
        while time.monotonic() < deadline:
            try:
                otp = extract_otp(read_current_email_text(driver))
                if otp:
                    return otp
            except Exception:
                pass
            time.sleep(1)
    return None


def open_new_tab(driver: webdriver.Chrome, timeout: int) -> str:
    existing_handles = driver.window_handles
    driver.execute_script("window.open('');")
    WebDriverWait(driver, timeout).until(EC.new_window_is_opened(existing_handles))
    return next(
        handle for handle in driver.window_handles if handle not in existing_handles
    )


def close_tab_and_return(
    driver: webdriver.Chrome, tab_handle: str, return_handle: str
) -> None:
    if tab_handle in driver.window_handles:
        driver.switch_to.window(tab_handle)
        driver.close()
    driver.switch_to.window(return_handle)


def get_otp_from_tempmail(
    driver: webdriver.Chrome,
    email: str,
    original_window: str,
    timeout: int = 5,
    otp_timeout: int = 120,
) -> str | None:
    username = email.strip().split("@", 1)[0]
    if not username:
        raise ValueError("Cannot create tempmail address: account email is empty.")

    print(f"Mailbox prefix: {username}")
    tempmail_window = open_new_tab(driver, timeout)
    driver.switch_to.window(tempmail_window)
    try:
        driver.get(TEMPMAIL_URL)
        wait_until_loaded(driver, timeout)
        if not fill_custom_email(driver, username, timeout):
            return None
        if not click_when_present(
            driver, CREATE_MAIL_BUTTON, "Create Email button", timeout
        ):
            return None
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(MAILBOX_ADDRESS)
        )
        print(f"Waiting for the first email for up to {otp_timeout}s...")
        otp = wait_for_first_email_otp(driver, otp_timeout)
        print(f"OTP extracted: {otp}" if otp else "OTP was not received in time.")
        return otp
    except Exception as error:
        print(f"TempMail flow failed: {error_summary(error)}")
        return None
    finally:
        close_tab_and_return(driver, tempmail_window, original_window)
        print("Returned to the login tab.")
