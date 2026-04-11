*** Settings ***
Library    test_library.py
Suite Teardown    Raise Teardown Failure

*** Test Cases ***
Should Fail From Suite Teardown
    No Operation
