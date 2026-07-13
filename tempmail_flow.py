from __future__ import annotations

import asyncio
import html
import re
import time
from urllib.parse import urljoin

import nodriver as uc

from nodriver_utils import (
    CSS,
    XPATH,
    Locator,
    click_element,
    click_when_present,
    error_summary,
    find_element,
    find_elements,
    navigate,
    replace_input,
    set_reactive_value,
    wait_until_loaded,
)


TEMPMAIL_URL = "https://tempmail.id.vn/en"
CUSTOM_MAIL_INPUT: Locator = (
    XPATH,
    "//input[@*[name()='wire:model']='customMail' "
    "or @placeholder='Input custom mail']",
)
CREATE_MAIL_BUTTON: Locator = (XPATH, "//button[normalize-space(.)='Create']")
MAILBOX_ADDRESS: Locator = (XPATH, "//button[contains(., '@')]")
INBOX_MESSAGE_LINKS: Locator = (CSS, "tr.fi-clickable a[href*='/message/']")
REFRESH_INBOX_BUTTON: Locator = (XPATH, "//button[normalize-space(.)='Refresh']")

XIAOMI_OTP_PATTERN = re.compile(
    r"verification\s+code\s*(?:is)?\s*:\s*([0-9]{4,8})",
    re.IGNORECASE,
)
CONTEXTUAL_OTP_PATTERN = re.compile(
    r"(?:otp|one[- ]?time(?:\s+pass(?:word|code))?|verification|verify|security)"
    r"[^\d]{0,80}([0-9]{4,8})",
    re.IGNORECASE,
)
GENERIC_OTP_PATTERN = re.compile(r"(?<!\d)([0-9]{4,8})(?!\d)")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


async def fill_custom_email(
    tab: uc.Tab,
    username: str,
    timeout: int = 5,
) -> bool:
    print("Waiting for custom mail input...")
    try:
        input_element = await find_element(tab, CUSTOM_MAIL_INPUT, timeout)
        await replace_input(input_element, username)
        await set_reactive_value(input_element, username)
        print(f"Custom mailbox name entered: {username}")
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


def html_to_text(content: str) -> str:
    return html.unescape(HTML_TAG_PATTERN.sub(" ", content))


async def read_current_email_text(tab: uc.Tab) -> str:
    text_parts: list[str] = []
    for frame_element in await tab.select_all("iframe[srcdoc]", timeout=0):
        source = frame_element.attrs.get("srcdoc")
        if source:
            text_parts.append(html_to_text(source))

    try:
        for frame in await tab.get_frames():
            try:
                text_parts.append(html_to_text(await frame.get_content()))
            except Exception:
                pass
    except Exception:
        pass

    if not text_parts:
        body = await find_element(tab, (CSS, "body"), timeout=2)
        text_parts.append(body.text_all)
    return "\n".join(text_parts)


async def refresh_inbox(tab: uc.Tab) -> None:
    refresh_buttons = await find_elements(tab, REFRESH_INBOX_BUTTON)
    if refresh_buttons:
        await click_element(refresh_buttons[0])


async def first_message_url(tab: uc.Tab) -> str | None:
    message_links = await find_elements(tab, INBOX_MESSAGE_LINKS)
    if not message_links:
        return None
    href = message_links[0].attrs.get("href")
    return urljoin(tab.target.url, href) if href else None


async def wait_for_first_email_otp(tab: uc.Tab, timeout: int) -> str | None:
    deadline = time.monotonic() + timeout
    message_opened = False
    while time.monotonic() < deadline:
        if not message_opened:
            message_url = await first_message_url(tab)
            if not message_url:
                await refresh_inbox(tab)
                await asyncio.sleep(2)
                continue

            print("First email received. Opening it...")
            await navigate(tab, message_url, timeout=10)
            message_opened = True

        try:
            otp = extract_otp(await read_current_email_text(tab))
            if otp:
                return otp
        except Exception:
            pass
        await asyncio.sleep(1)
    return None


async def get_otp_from_tempmail(
    browser: uc.Browser,
    email: str,
    original_tab: uc.Tab,
    timeout: int = 5,
    otp_timeout: int = 120,
) -> str | None:
    username = email.strip().split("@", 1)[0]
    if not username:
        raise ValueError("Cannot create tempmail address: account email is empty.")

    print(f"Mailbox prefix: {username}")
    tempmail_tab = await browser.get(TEMPMAIL_URL, new_tab=True)
    try:
        await wait_until_loaded(tempmail_tab, timeout)
        if not await fill_custom_email(tempmail_tab, username, timeout):
            return None
        if not await click_when_present(
            tempmail_tab,
            CREATE_MAIL_BUTTON,
            "Create Email button",
            timeout,
        ):
            return None
        await find_element(tempmail_tab, MAILBOX_ADDRESS, timeout)
        print(f"Waiting for the first email for up to {otp_timeout}s...")
        otp = await wait_for_first_email_otp(tempmail_tab, otp_timeout)
        print(f"OTP extracted: {otp}" if otp else "OTP was not received in time.")
        return otp
    except Exception as error:
        print(f"TempMail flow failed: {error_summary(error)}")
        return None
    finally:
        try:
            await tempmail_tab.close()
        finally:
            await original_tab.bring_to_front()
            print("Returned to the login tab.")
