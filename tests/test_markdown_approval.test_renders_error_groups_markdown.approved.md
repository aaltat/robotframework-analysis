# Error Groups Suite Test Summary

- Total: 4
- Passed: 1
- Failed: 3
- Skipped: 0
- Start / end: 20260101 00:00:00.000 / 20260101 00:00:00.000

# Error Group 1: ValueError

ValueError: database connection failed: unable to connect to server at host.example.com:5432, connection timeout after 30 seconds, please check your database credentials and network connectivity

## Group 1 Tests
| Suite Name | Test Name | Path |
| --- | --- | --- |
| Error Groups Suite | Database Error One | tests/fixtures/error_groups_suite.robot |
| Error Groups Suite | Database Error Two | tests/fixtures/error_groups_suite.robot |

# Error Group 2: TypeError

TypeError: TypeError: expected argument of type str or bytes-like object, not NoneType. Function signature requires (name: str, age: int, email: str, phone: str, address: str, city: str, state: str, zip_code: str, country: str, company: str, job_title: str, department: str, manager: str, salary: int…

## Group 2 Tests
| Suite Name | Test Name | Path |
| --- | --- | --- |
| Error Groups Suite | Login Timeout | tests/fixtures/error_groups_suite.robot |
