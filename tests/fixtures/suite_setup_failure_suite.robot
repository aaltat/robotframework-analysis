*** Settings ***
Library    test_library.py
Suite Setup    Raise Setup Failure

*** Test Cases ***
Should Fail From Suite Setup
    No Operation
