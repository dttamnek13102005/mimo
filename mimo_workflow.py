from __future__ import annotations

import argparse
import time
from pathlib import Path

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
from tempmail_flow import get_otp_from_tempmail


PROMPT_PATH = Path(__file__).resolve().with_name("prompt.txt")
WORKSPACE_WAIT_SECONDS = 120
POST_SEND_WAIT_SECONDS = 120

TRY_NOW_BUTTON: Locator = (
    By.XPATH, "//button[contains(normalize-space(.), 'Try Now')]"
)
CREATE_NOW_BUTTON: Locator = (
    By.CSS_SELECTOR, "button[data-track-id='claw_welcome_create_btn']"
)
TERMS_CHECKBOX: Locator = (By.CSS_SELECTOR, "input.ant-checkbox-input[type='checkbox']")
ACCOUNT_INPUT: Locator = (By.CSS_SELECTOR, "input[name='account']")
PASSWORD_INPUT: Locator = (By.CSS_SELECTOR, "input[name='password']")
SIGN_IN_BUTTON: Locator = (
    By.XPATH, "//button[@type='submit' and contains(., 'Sign in')]"
)
SEND_EMAIL_BUTTON: Locator = (
    By.XPATH, "//button[@type='submit' and contains(., 'Send')]"
)
OTP_INPUT: Locator = (By.CSS_SELECTOR, "input[name='ticket'][placeholder='Enter code']")
OTP_SUBMIT_BUTTON: Locator = (
    By.XPATH,
    "//button[@type='submit' and not(@disabled) and .//span[normalize-space(.)='Submit']]",
)
CREATE_CONFIRMATION_CHECKBOX: Locator = (
    By.XPATH,
    "//button[@data-track-id='claw_create_confirm_btn']"
    "/ancestor::*[.//button[@role='checkbox']][1]"
    "//button[@role='checkbox' and @aria-disabled='false'][1]",
)
CONTINUE_CREATING_BUTTON: Locator = (
    By.CSS_SELECTOR, "button[data-track-id='claw_create_confirm_btn']"
)
PROMPT_TEXTAREA: Locator = (
    By.CSS_SELECTOR,
    "textarea[placeholder='Ask me anything! Hold Shift+Enter to start a new line.']",
)
SEND_PROMPT_BUTTON: Locator = (
    By.CSS_SELECTOR, "button[data-track-id='claw_send_btn']"
)


def fill_login_credentials(
    driver: webdriver.Chrome,
    account: str,
    password: str,
    timeout: int = 5,
) -> bool:
    print("Waiting for login inputs...")
    try:
        wait = WebDriverWait(driver, timeout)
        account_input = wait.until(EC.element_to_be_clickable(ACCOUNT_INPUT))
        password_input = wait.until(EC.element_to_be_clickable(PASSWORD_INPUT))
        replace_with_keyboard(driver, account_input, account)
        replace_with_keyboard(driver, password_input, password)
        print("Login credentials entered.")
        return True
    except Exception as error:
        print(f"Could not enter login credentials: {error_summary(error)}")
        return False


def submit_otp(driver: webdriver.Chrome, otp: str, timeout: int = 10) -> bool:
    print("Waiting for the verification-code input...")
    try:
        wait = WebDriverWait(driver, timeout)
        ticket_input = wait.until(EC.element_to_be_clickable(OTP_INPUT))
        replace_with_keyboard(driver, ticket_input, otp)
        wait.until(lambda browser: ticket_input.get_attribute("value") == otp)
        submit_button = wait.until(EC.element_to_be_clickable(OTP_SUBMIT_BUTTON))
        click_element(driver, submit_button)
        print("OTP submitted.")
        return True
    except Exception as error:
        print(f"Could not submit the OTP: {error_summary(error)}")
        return False


def ensure_creation_confirmation(
    driver: webdriver.Chrome, timeout: int = 10
) -> bool:
    print("Checking the creation confirmation...")
    try:
        wait = WebDriverWait(driver, timeout)
        checkbox = wait.until(EC.presence_of_element_located(CREATE_CONFIRMATION_CHECKBOX))
        if checkbox.get_attribute("aria-checked") != "true":
            checkbox = wait.until(EC.element_to_be_clickable(CREATE_CONFIRMATION_CHECKBOX))
            click_element(driver, checkbox)
            wait.until(
                lambda browser: browser.find_element(
                    *CREATE_CONFIRMATION_CHECKBOX
                ).get_attribute("aria-checked")
                == "true"
            )
            print("Creation confirmation checked.")
        else:
            print("Creation confirmation was already checked.")

        continue_button = wait.until(EC.element_to_be_clickable(CONTINUE_CREATING_BUTTON))
        click_element(driver, continue_button)
        print("Clicked 'Continue Creating'.")
        return True
    except Exception as error:
        print(f"Could not confirm creation: {error_summary(error)}")
        return False


def load_prompt(prompt_path: Path) -> str:
    prompt_text = prompt_path.read_text(encoding="utf-8-sig").strip()
    if not prompt_text:
        raise ValueError(f"Prompt file is empty: {prompt_path}")
    return prompt_text


def send_prompt_after_creation(
    driver: webdriver.Chrome,
    prompt_path: Path,
    wait_seconds: int = WORKSPACE_WAIT_SECONDS,
    timeout: int = 30,
) -> bool:
    try:
        prompt_text = load_prompt(prompt_path)
        print(f"Waiting {wait_seconds}s for the workspace to become ready...")
        time.sleep(wait_seconds)
        wait = WebDriverWait(driver, timeout)
        textarea = wait.until(EC.element_to_be_clickable(PROMPT_TEXTAREA))
        set_reactive_value(driver, textarea, prompt_text, timeout)
        send_button = wait.until(EC.element_to_be_clickable(SEND_PROMPT_BUTTON))
        click_element(driver, send_button)
        print("Prompt sent.")
        print(
            f"Waiting {POST_SEND_WAIT_SECONDS}s after sending before closing "
            "the browser..."
        )
        time.sleep(POST_SEND_WAIT_SECONDS)
        return True
    except Exception as error:
        print(f"Could not send prompt: {error_summary(error)}")
        return False


def request_verification_code(
    driver: webdriver.Chrome, account: str, password: str
) -> bool:
    click_when_present(driver, TRY_NOW_BUTTON, "Try Now")
    click_when_present(driver, CREATE_NOW_BUTTON, "Create Now")
    click_when_present(driver, TERMS_CHECKBOX, "Checkbox")
    if not fill_login_credentials(driver, account, password):
        return False
    if not click_when_present(driver, SIGN_IN_BUTTON, "Sign in"):
        return False
    return click_when_present(driver, SEND_EMAIL_BUTTON, "Send Email")


def complete_creation_flow(driver: webdriver.Chrome, otp: str) -> bool:
    if not submit_otp(driver, otp):
        return False
    if not click_when_present(
        driver, CREATE_NOW_BUTTON, "Create Now after OTP", timeout=10
    ):
        return False
    if not ensure_creation_confirmation(driver):
        return False
    return send_prompt_after_creation(driver, PROMPT_PATH)


def save_screenshot(driver: webdriver.Chrome, screenshot_path: str) -> None:
    output_path = Path(screenshot_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(output_path))
    print(f"Screenshot saved: {output_path}")


def run_workflow(driver: webdriver.Chrome, args: argparse.Namespace) -> bool:
    account = args.account.strip()
    password = args.password
    print(f"Opening: {args.url}")
    driver.get(args.url)
    wait_until_loaded(driver, args.timeout)
    print(f"Loaded URL: {driver.current_url}")
    print(f"Page title: {driver.title}")

    if not request_verification_code(driver, account, password):
        return False

    login_window = driver.current_window_handle
    otp = get_otp_from_tempmail(
        driver,
        account,
        original_window=login_window,
        timeout=5,
        otp_timeout=args.otp_timeout,
    )
    completed = bool(otp) and complete_creation_flow(driver, otp)
    if args.screenshot:
        save_screenshot(driver, args.screenshot)
    return completed
