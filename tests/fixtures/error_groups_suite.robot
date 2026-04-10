*** Settings ***
Library    test_library.py

*** Test Cases ***
Passing
    No Operation
Database Error One
    Raise Value Error
Database Error Two
    Raise Value Error
Login Timeout
    Raise Logged Type Error
Printed Failure
    Raise Printed Assertion Error
