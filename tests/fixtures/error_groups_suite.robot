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

*** Keywords ***
Keyword One
    No Operation

Keyword Two
    No Operation

Keyword Three
    Sub Keyword 3.1

Sub Keyword 3.1
    IF    ${True}
        Sub Keyword 3.1.1
    END

Sub Keyword 3.1.1
    No Operation
    Raise Logged Type Error
    No Operation
