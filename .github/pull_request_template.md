## Summary

Describe the user-visible or engineering outcome.

## Verification

- [ ] `ruff check app tests`
- [ ] `pytest`
- [ ] `docker build -t feiyu:local .`

## Risk review

- [ ] No secrets or credentials are included.
- [ ] Workflow or permission changes are called out explicitly.
- [ ] Security-sensitive input and process execution paths were reviewed.
