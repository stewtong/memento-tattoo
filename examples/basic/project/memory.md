# Project Memory

## Key Decisions

- Keep every package in one repository, and let CI test only the packages whose files changed so pull requests stay fast.
- Rename public functions in one change that also updates their callers.

## Current state

<!-- delta:sess_demo.project.11111111 -->
- Situation: billing package API rename
- Note: `format_amount` is now `format_money`; the checkout package's caller was updated in the same change.
