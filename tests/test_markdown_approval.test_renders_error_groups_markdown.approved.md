# Error Groups Suite Test Summary

- Total: 5
- Passed: 1
- Failed: 4
- Skipped: 0
- Start / end: 20260101 00:00:00.000 / 20260101 00:00:00.000

# Error Group 1: ValueError

ValueError: database connection failed: unable to connect to server at host.example.com:5432, connection timeout after 30 seconds, please check your database credentials and network connectivity

## Group 1 Tests
| Suite Name | Test Name | Path | More Details |
| --- | --- | --- | --- |
| Error Groups Suite | Database Error One | tests/fixtures/error_groups_suite.robot | .robotframework_analysis/group_001_Error_Groups_Suite_Database_Error_One_001.md |
| Error Groups Suite | Database Error Two | tests/fixtures/error_groups_suite.robot | .robotframework_analysis/group_001_Error_Groups_Suite_Database_Error_Two_002.md |

# Error Group 2: TypeError

TypeError: TypeError: expected argument of type str or bytes-like object, not NoneType. Function signature requires (name: str, age: int, email: str, phone: str, address: str, city: str, state: str, zip_code: str, country: str, company: str, job_title: str, department: str, manager: str, salary: int…

## Group 2 Tests
| Suite Name | Test Name | Path | More Details |
| --- | --- | --- | --- |
| Error Groups Suite | Login Timeout | tests/fixtures/error_groups_suite.robot | .robotframework_analysis/group_002_Error_Groups_Suite_Login_Timeout_001.md |

# Error Group 3

assertion failed: expected status code 200 but got 403, indicating insufficient permissions. The user account may not have the required role or scope to access this resource

## Group 3 Tests
| Suite Name | Test Name | Path | More Details |
| --- | --- | --- | --- |
| Error Groups Suite | Printed Failure | tests/fixtures/error_groups_suite.robot | .robotframework_analysis/group_003_Error_Groups_Suite_Printed_Failure_001.md |
