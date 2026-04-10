# Error Groups Suite Login Timeout error

TypeError: TypeError: expected argument of type str or bytes-like object, not NoneType. Function signature requires (name: str, age: int, email: str, phone: str, address: str, city: str, state: str, zip_code: str, country: str, company: str, job_title: str, department: str, manager: str, salary: int, hire_date: str, termination_date: str, is_active: bool, is_admin: bool) but received NoneType for parameter 'name'. This is typically caused by passing None where a string is expected. To fix this, ensure all required string parameters are properly initialized before calling this function. You may want to check your data source, API response, or configuration file to ensure values are not null. The full traceback shows the call originated from line 42 in process_user_data() which was called from setup_database() at line 18.

# Log message
timestamp INFO: log messages goes here 1
timestamp INFO: html info message
timestamp DEBUG: log messages goes here 2
timestamp DEBUG: html debug message
timestamp WARN: log messages goes here 3
timestamp WARN: <removed html>
timestamp TRACE: log messages goes here 4

# Keyword leaf
Login Timeout
└── Test Body
    ├── Keyword One    PASS
    ├── Keyword Two    PASS
    └── Keyword Three    FAIL
        └── Sub Keyword 3.1    FAIL
            └── IF/ELSE ROOT    FAIL
                └── IF    FAIL
                    └── Sub Keyword 3.1.1    FAIL
                        ├── No Operation    PASS
                        └── Raise Logged Type Error    FAIL
                            Error: TypeError: TypeError: expected argument of type st…
