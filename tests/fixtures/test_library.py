"""Test fixture library for raising different exception types."""

import base64
from pathlib import Path

from robot.api import logger

_MINIMAL_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWj"
    "R9awAAAABJRU5ErkJggg=="
)
_MINIMAL_PNG = base64.b64decode(_MINIMAL_PNG_B64)


def raise_value_error() -> None:
    """Raise a ValueError with a realistic message."""
    raise ValueError(
        "database connection failed: unable to connect to server at "
        "host.example.com:5432, connection timeout after 30 seconds, "
        "please check your database credentials and network connectivity"
    )


def raise_type_error() -> None:
    """Raise a TypeError with a very long message."""
    long_message = (
        "TypeError: expected argument of type str or bytes-like object, "
        "not NoneType. Function signature requires (name: str, age: int, "
        "email: str, phone: str, address: str, city: str, state: str, "
        "zip_code: str, country: str, company: str, job_title: str, "
        "department: str, manager: str, salary: int, hire_date: str, "
        "termination_date: str, is_active: bool, is_admin: bool) but "
        "received NoneType for parameter 'name'. This is typically caused "
        "by passing None where a string is expected. To fix this, ensure "
        "all required string parameters are properly initialized before "
        "calling this function. You may want to check your data source, "
        "API response, or configuration file to ensure values are not null. "
        "The full traceback shows the call originated from line 42 in "
        "process_user_data() which was called from setup_database() at line 18."
    )
    raise TypeError(long_message)


def raise_logged_type_error() -> None:
    """Emit logger messages before raising a TypeError."""
    logger.info("log messages goes here 1")
    logger.info("<div><b>html</b> info message</div>")
    logger.debug("log messages goes here 2")
    logger.debug('<span class="x">html debug message</span>')
    logger.warn("log messages goes here 3")
    logger.warn('<img src="data:image/png;base64,AAAA" />')
    logger.trace("log messages goes here 4")
    raise_type_error()


def raise_assertion_error() -> None:
    """Raise an AssertionError with a detailed message."""
    raise AssertionError(
        "assertion failed: expected status code 200 but got 403, "
        "indicating insufficient permissions. The user account may not "
        "have the required role or scope to access this resource"
    )


def raise_printed_assertion_error() -> None:
    """Emit print output before raising an AssertionError."""
    print("printed output goes here 1")
    print("printed output goes here 2")
    raise_assertion_error()


def raise_setup_failure() -> None:
    """Raise a setup-specific runtime error."""
    raise RuntimeError("setup failed while preparing test preconditions")


def raise_teardown_failure() -> None:
    """Raise a teardown-specific runtime error."""
    raise RuntimeError("teardown failed while cleaning test resources")


def raise_with_file_screenshot(output_dir: str) -> None:
    """Create a PNG file in output_dir, log it as an href link, then fail."""
    screenshot_path = Path(output_dir) / "screenshot_file_link.png"
    screenshot_path.write_bytes(_MINIMAL_PNG)
    logger.info('<a href="screenshot_file_link.png">screenshot</a>', html=True)
    raise AssertionError("failed with file screenshot")


def raise_with_embedded_screenshot() -> None:
    """Log a base64-encoded PNG as an embedded image, then fail."""
    logger.info(
        f'<img alt="screenshot" src="data:image/png;base64,{_MINIMAL_PNG_B64}" />',
        html=True,
    )
    raise AssertionError("failed with embedded screenshot")
