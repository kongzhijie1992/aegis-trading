## Problem and result

Describe the trigger and resulting behavior. Name the affected libraries.

## Validation

- [ ] `poetry run python scripts/quality.py` passes.
- [ ] Dependency audit passes without an ignored advisory.
- [ ] Built wheels pass clean-environment tests.
- [ ] API/dependency/version changes and migration steps are documented.
- [ ] Both self-review passes are recorded: correctness/safety, then packaging/security.
- [ ] No credentials, account config, runtime logs or broker submissions are included.

## Risks and recovery

Describe unresolved limits and how to roll back code without deleting order history.
