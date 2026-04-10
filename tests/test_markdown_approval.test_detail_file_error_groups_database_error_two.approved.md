# Error Groups Suite Database Error Two error

ValueError: database connection failed: unable to connect to server at host.example.com:5432, connection timeout after 30 seconds, please check your database credentials and network connectivity

# Origin
- Test file: tests/fixtures/error_groups_suite.robot
- Failing library: test_library

# Keyword leaf
tests/fixtures/error_groups_suite.robot.Database Error Two
└── Test Body
    └── test_library.Raise Value Error    FAIL
        Error: ValueError: database connection failed: unable to …
