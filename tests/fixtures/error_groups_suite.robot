*** Settings ***
Library    test_library.py
Resource    error_groups_keywords.resource

*** Test Cases ***
Passing
    No Operation
Database Error One
    Raise Value Error
Database Error Two
    Raise Value Error
Login Timeout
    Keyword One
    Keyword Two
    Keyword Three
Printed Failure
    Raise Printed Assertion Error
Setup Failure Case
    [Setup]    Raise Setup Failure
    No Operation
Teardown Failure Case
    No Operation
    [Teardown]    Raise Teardown Failure
