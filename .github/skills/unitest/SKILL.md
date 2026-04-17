---
name: unitest
description: Unite test best practices for Robot Framework analysis code.
requirements:
  - pytest
  - pytest-cov
  - mypy
  - ruff
---
# Robot Framework analysis unit testing best practices
Unittest test must be written by using pytest. Test must be readable and
written in a that they do not require comments.

# Development model
User will specify high level approval file, by using Python Approval test,
which is just an example. Then functionality will be implemented in a way that
is satisfies the approval test intentions. Implementation details can change
the approved file. Approval file is just an example of the expected output, not a strict contract.

Other unit tests can be written to verify the implementation details, but they are
not the main focus. The main focus is to satisfy the approval test intentions.

After approval test is satisfied, run all pytest and perform code coverage analysis.
Aim for 90% or more code coverage. Run also mypy and ruff to ensure code quality and
type safety.

After all tests are passing and code quality is good, let user review the approved
file, read the code and other tests to ensure that the implementation is correct and
maintainable.
