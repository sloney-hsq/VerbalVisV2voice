# Privacy and research-use guidance

## Local logging boundary

Local runs can record conversation text, tool arguments, dashboard state,
response and transaction metadata, and timestamps under `backend/logs/`.
The runtime writes event and conversation traces there for local inspection.
Those logs are ignored by Git. Real participant traces must not be committed,
attached to issues, or included in release artifacts.

This is a single-participant local prototype boundary, not a multi-user data
platform or a remote logging service.

## Minimum research-use protocol

Before collecting or retaining participant material, the research operator
must:

- obtain consent appropriate to the study and explain what local traces may
  contain;
- restrict trace access to authorised study personnel and protect copies;
- set and follow a retention and deletion decision for the study material; and
- review traces for identifiers and anonymisation needs before sharing,
  analysis, or publication.

Use synthetic or scrubbed data when demonstrating logs. Delete or securely
remove traces according to the study's retention decision; do not treat an
ignored path as a deletion policy.

## Boundary of this document

This document is operational guidance for local research use. It is not legal
advice, privacy advice, or compliance certification.
