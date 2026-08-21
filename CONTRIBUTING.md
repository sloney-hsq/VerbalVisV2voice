# Contributing

Thanks for improving VerbalVis and the DataOps Agent runtime. This is a public
portfolio repository, so changes should be small, reproducible, and easy for a
reviewer to verify.

## Before you start

1. Search existing issues and documentation for relevant design decisions.
2. Open an issue or discussion first for a new capability or a cross-cutting
   architecture change.
3. Keep pull requests focused. Do not mix refactors, dependency upgrades, and
   new behavior unless they are necessary for the same change.

## Development boundaries

- The existing VerbalVis experimental application keeps its single-session
  behavior. Reusable runtime pieces belong in the DataOps Agent integration
  boundary rather than silently changing that behavior.
- Treat structured facts, retrieval knowledge, and runtime state as separate
  concerns: DuckDB/SQL for deterministic facts, retrieval for documentation
  and guidance, and Redis for ephemeral coordination and caching.
- DataOps ingestion, quality rules, task state, and traces must remain
  deterministic and testable without a hosted Redis or Elasticsearch service.
- Do not commit real customer data, private datasets, API keys, tokens,
  embeddings derived from restricted material, or unredacted execution traces.
  Use minimal synthetic fixtures instead.

## Local checks

Create and activate the Python environment described in
`requirements-dataops.txt`, then run the relevant checks from the repository
root:

```powershell
python -m pytest tests/dataops -q
python -m pytest tests -q
python -m compileall dataops_agent
```

For a frontend change, also run:

```powershell
Push-Location frontend
npm test
npm run build
Pop-Location
```

If a change needs Redis or Elasticsearch behavior, add a deterministic unit
test with a fake client and, where practical, document a Docker Compose smoke
test. Do not make the core test suite depend on a shared external service.

## Pull request checklist

- [ ] The implementation and tests describe the same behavior.
- [ ] New failure modes have explicit errors, retry/idempotency semantics, or
      a documented boundary.
- [ ] Trace data is useful for debugging but contains no secrets or raw
      sensitive payloads.
- [ ] Documentation and examples do not claim unmeasured performance or a
      production deployment that has not occurred.
- [ ] `git diff --check` and the relevant local checks pass.
