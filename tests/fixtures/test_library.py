"""Test fixture library for raising different exception types."""


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


def raise_assertion_error() -> None:
    """Raise an AssertionError with a detailed message."""
    raise AssertionError(
        "assertion failed: expected status code 200 but got 403, "
        "indicating insufficient permissions. The user account may not "
        "have the required role or scope to access this resource"
    )
