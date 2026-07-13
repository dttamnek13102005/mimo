from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import nodriver as uc

from nodriver_utils import (
    CSS,
    XPATH,
    Locator,
    click_element,
    click_when_present,
    error_summary,
    find_element,
    replace_input,
    set_reactive_value,
    wait_for_attribute,
    wait_until_loaded,
)
from tempmail_flow import get_otp_from_tempmail


PROMPT_PATH = Path(__file__).resolve().with_name("prompt.txt")
WORKSPACE_WAIT_SECONDS = 120
POST_SEND_WAIT_SECONDS = 120
ENV_PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")

TRY_NOW_BUTTON: Locator = (
    XPATH,
    "//button[contains(normalize-space(.), 'Try Now')]",
)
CREATE_NOW_BUTTON: Locator = (
    CSS,
    "button[data-track-id='claw_welcome_create_btn']",
)
TERMS_CHECKBOX: Locator = (CSS, "input.ant-checkbox-input[type='checkbox']")
ACCOUNT_INPUT: Locator = (CSS, "input[name='account']")
PASSWORD_INPUT: Locator = (CSS, "input[name='password']")
SIGN_IN_BUTTON: Locator = (
    XPATH,
    "//button[@type='submit' and contains(., 'Sign in')]",
)
SEND_EMAIL_BUTTON: Locator = (
    XPATH,
    "//button[@type='submit' and contains(., 'Send')]",
)
OTP_INPUT: Locator = (CSS, "input[name='ticket'][placeholder='Enter code']")
OTP_SUBMIT_BUTTON: Locator = (
    XPATH,
    "//button[@type='submit' and not(@disabled) "
    "and .//span[normalize-space(.)='Submit']]",
)
CREATE_CONFIRMATION_CHECKBOX: Locator = (
    XPATH,
    "//button[@data-track-id='claw_create_confirm_btn']"
    "/ancestor::*[.//button[@role='checkbox']][1]"
    "//button[@role='checkbox' and @aria-disabled='false'][1]",
)
CONTINUE_CREATING_BUTTON: Locator = (
    CSS,
    "button[data-track-id='claw_create_confirm_btn']",
)
PROMPT_TEXTAREA: Locator = (
    CSS,
    "textarea[placeholder='Ask me anything! Hold Shift+Enter to start a new line.']",
)
SEND_PROMPT_BUTTON: Locator = (
    CSS,
    "button[data-track-id='claw_send_btn']",
)


async def fill_login_credentials(
    tab: uc.Tab,
    account: str,
    password: str,
    timeout: int = 5,
) -> bool:
    print("Waiting for login inputs...")
    try:
        account_input = await find_element(tab, ACCOUNT_INPUT, timeout)
        password_input = await find_element(tab, PASSWORD_INPUT, timeout)
        await replace_input(account_input, account)
        await replace_input(password_input, password)
        print("Login credentials entered.")
        return True
    except Exception as error:
        print(f"Could not enter login credentials: {error_summary(error)}")
        return False


async def submit_otp(tab: uc.Tab, otp: str, timeout: int = 10) -> bool:
    print("Waiting for the verification-code input...")
    try:
        ticket_input = await find_element(tab, OTP_INPUT, timeout)
        await replace_input(ticket_input, otp)
        submit_button = await find_element(tab, OTP_SUBMIT_BUTTON, timeout)
        await click_element(submit_button)
        print("OTP submitted.")
        return True
    except Exception as error:
        print(f"Could not submit the OTP: {error_summary(error)}")
        return False


async def ensure_creation_confirmation(tab: uc.Tab, timeout: int = 10) -> bool:
    print("Checking the creation confirmation...")
    try:
        checkbox = await find_element(tab, CREATE_CONFIRMATION_CHECKBOX, timeout)
        if checkbox.attrs.get("aria-checked") != "true":
            await click_element(checkbox)
            await wait_for_attribute(
                tab,
                CREATE_CONFIRMATION_CHECKBOX,
                "aria-checked",
                "true",
                timeout,
            )
            print("Creation confirmation checked.")
        else:
            print("Creation confirmation was already checked.")

        continue_button = await find_element(tab, CONTINUE_CREATING_BUTTON, timeout)
        await click_element(continue_button)
        print("Clicked 'Continue Creating'.")
        return True
    except Exception as error:
        print(f"Could not confirm creation: {error_summary(error)}")
        return False


def load_prompt(prompt_path: Path) -> str:
    prompt_text = prompt_path.read_text(encoding="utf-8-sig").strip()
    if not prompt_text:
        raise ValueError(f"Prompt file is empty: {prompt_path}")

    variable_names = set(ENV_PLACEHOLDER_PATTERN.findall(prompt_text))
    missing_names = sorted(name for name in variable_names if not os.environ.get(name))
    if missing_names:
        raise ValueError(
            "Missing environment variable(s) required by prompt.txt: "
            + ", ".join(missing_names)
        )
    return ENV_PLACEHOLDER_PATTERN.sub(
        lambda match: os.environ[match.group(1)], prompt_text
    )


async def send_prompt_after_creation(
    tab: uc.Tab,
    prompt_path: Path,
    wait_seconds: int = WORKSPACE_WAIT_SECONDS,
    timeout: int = 30,
) -> bool:
    try:
        prompt_text = load_prompt(prompt_path)
        print(f"Waiting up to {wait_seconds + timeout}s for the workspace...")
        textarea = await find_element(
            tab,
            PROMPT_TEXTAREA,
            timeout=wait_seconds + timeout,
        )
        await set_reactive_value(textarea, prompt_text)
        send_button = await find_element(tab, SEND_PROMPT_BUTTON, timeout)
        await click_element(send_button)
        print("Prompt sent.")
        print(
            f"Waiting {POST_SEND_WAIT_SECONDS}s after sending before closing "
            "the browser..."
        )
        await tab.sleep(POST_SEND_WAIT_SECONDS)
        return True
    except Exception as error:
        print(f"Could not send prompt: {error_summary(error)}")
        return False


async def request_verification_code(
    tab: uc.Tab,
    account: str,
    password: str,
) -> bool:
    await click_when_present(tab, TRY_NOW_BUTTON, "Try Now")
    await click_when_present(tab, CREATE_NOW_BUTTON, "Create Now")
    await click_when_present(tab, TERMS_CHECKBOX, "Checkbox")
    if not await fill_login_credentials(tab, account, password):
        return False
    if not await click_when_present(tab, SIGN_IN_BUTTON, "Sign in"):
        return False
    return await click_when_present(tab, SEND_EMAIL_BUTTON, "Send Email")


async def complete_creation_flow(tab: uc.Tab, otp: str) -> bool:
    if not await submit_otp(tab, otp):
        return False
    if not await click_when_present(
        tab,
        CREATE_NOW_BUTTON,
        "Create Now after OTP",
        timeout=10,
    ):
        return False
    if not await ensure_creation_confirmation(tab):
        return False
    return await send_prompt_after_creation(tab, PROMPT_PATH)


async def save_screenshot(tab: uc.Tab, screenshot_path: str) -> None:
    output_path = Path(screenshot_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image_format = "png" if output_path.suffix.lower() == ".png" else "jpeg"
    await tab.save_screenshot(str(output_path), format=image_format)
    print(f"Screenshot saved: {output_path}")


async def run_workflow(
    browser: uc.Browser,
    tab: uc.Tab,
    args: argparse.Namespace,
) -> bool:
    account = args.account.strip()
    password = args.password
    print(f"Opening: {args.url}")
    await wait_until_loaded(tab, args.timeout)
    await tab
    print(f"Loaded URL: {tab.target.url}")
    print(f"Page title: {tab.target.title}")

    if not await request_verification_code(tab, account, password):
        return False

    otp = await get_otp_from_tempmail(
        browser,
        account,
        original_tab=tab,
        timeout=5,
        otp_timeout=args.otp_timeout,
    )
    completed = bool(otp) and await complete_creation_flow(tab, otp)
    if args.screenshot:
        await save_screenshot(tab, args.screenshot)
    return completed
