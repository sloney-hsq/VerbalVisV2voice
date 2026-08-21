# Security Policy

## Supported versions

Security fixes are considered for the latest version on the default branch.
This repository is a portfolio project; compatibility or response-time
guarantees are not offered.

## Reporting a vulnerability

Please do **not** open a public issue, discussion, pull request, or pastebin
for a suspected vulnerability. Do not include API keys, access tokens, private
datasets, production logs, or other secrets in a report.

Use the repository's **Security** tab to create a private GitHub Security
Advisory. If private advisories are not enabled, contact the repository owner
through the contact method listed in the repository profile and include only
the minimum information needed to reproduce the issue safely.

A useful report includes:

- the affected commit or release;
- a concise impact assessment;
- safe reproduction steps or a minimal proof of concept;
- suggested mitigations, if known.

The maintainer will acknowledge reports when review is possible, assess the
scope, and coordinate a fix or a public disclosure when appropriate. Please
allow reasonable time for investigation before sharing details publicly.

## Local development

Never commit secrets. Keep credentials in local environment variables or
untracked `.env` files, use synthetic/sanitized fixtures in tests, and redact
tokens, authorization headers, and personally identifiable information from
traces and issue reports.
