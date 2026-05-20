# ERRORS.md — TrailPrint3D Web Conversion

## Format
After any approach fails twice, add a dated entry:
- **Attempted**: approach that failed
- **Failed Because**: root cause
- **What Worked Instead**: working approach
- **Note for Next Time**: guidance
- **Flagged By**: role

---

### 2026-05-20 — Deferred import not patchable in tests

- **Attempted**: `patch("app.routes.jobs.settings")` with `settings` imported inside the route function body.
- **Failed Because**: Python's `unittest.mock.patch` can only patch module-level names. A name imported inside a function is a local variable at call time, not a module attribute.
- **What Worked Instead**: Import `settings` at the top of `app/routes/jobs.py`; the patch target then resolves correctly.
- **Note for Next Time**: Always import shared singletons at module level. Deferred imports are only safe for breaking circular imports, never for testability.
- **Flagged By**: Integration Lead
