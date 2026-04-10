# Error Groups Suite Printed Failure error

assertion failed: expected status code 200 but got 403, indicating insufficient permissions. The user account may not have the required role or scope to access this resource

# Log message
timestamp INFO: printed output goes here 1
printed output goes here 2

# Origin
- Test file: tests/fixtures/error_groups_suite.robot
- Failing library: test_library

# Keyword leaf
tests/fixtures/error_groups_suite.robot.Printed Failure
└── Test Body
    └── test_library.Raise Printed Assertion Error    FAIL
        Error: assertion failed: expected status code 200 but got…
