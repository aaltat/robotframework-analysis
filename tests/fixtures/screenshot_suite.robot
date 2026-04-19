*** Settings ***
Library    test_library.py

*** Test Cases ***
Screenshot Via File Link
    Raise With File Screenshot    ${OUTPUT DIR}

Screenshot Via Embedded Image
    Raise With Embedded Screenshot
