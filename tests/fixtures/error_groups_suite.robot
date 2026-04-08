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
    Raise Type Error
