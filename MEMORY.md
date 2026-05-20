# MEMORY.md

Decision log for the TrailPrint3D web app conversion. Every significant decision
is appended here with full reasoning. Read this file at the start of every
session before suggesting changes.

## Format

Each entry uses these fields:

- **Decided**: what was chosen
- **Why**: reasoning
- **Rejected**: alternatives considered
- **Rejected Why**: why they were discarded
- **Flagged By**: role of the agent making the decision
- **Confidence**: High / Medium / Low

---

## 2026-05-20 - Session 1: Project bootstrap

### Initial state

- **Decided**: Bootstrap project on branch `claude/analyze-trailprint3d-Ub11X`. Repository contains the upstream `TrailPrint3D/` Blender addon source and a real-world GPX (`Cluj_Eco_Trail.gpx`, ~2.3 MB).
- **Why**: This is the agreed development branch per the task brief. Both files are needed for analysis and integration testing.
- **Rejected**: Working on `main`; generating a synthetic test GPX from scratch.
- **Rejected Why**: Brief mandates a feature branch; a real GPX is already present and is more representative than a synthetic one.
- **Flagged By**: Integration Lead
- **Confidence**: High

### Q1 - Standard integration test GPX

- **Decided**: Use `Cluj_Eco_Trail.gpx` (already in repo root, ~2.3 MB real-world track) as the single standard integration test fixture.
- **Why**: Real-world data, representative of typical user uploads, already present. No need to fabricate a synthetic track for Phase 1.
- **Rejected**: Adding a small synthetic GPX alongside; using only a synthetic GPX.
- **Rejected Why**: Avoid premature complexity (Rule 2). If the Cluj track proves too large/slow for unit tests during pipeline implementation, we can add a small synthetic one then.
- **Flagged By**: User
- **Confidence**: High

### Q2 - Visual design source

- **Decided**: Establish a Tailwind-based design token system directly in the codebase. Do not wait for Figma.
- **Why**: Unblocks frontend work immediately, no external dependency. Tokens (colors, spacing, typography) can be refined later if Figma arrives.
- **Rejected**: Wait for Figma specs; hybrid placeholder-then-refactor.
- **Rejected Why**: Waiting blocks Phase 5. Hybrid was not explicitly chosen and adds a refactor step.
- **Flagged By**: User
- **Confidence**: High

### Q3 - Job state persistence

- **Decided**: Ephemeral Redis-backed job state only. No PostgreSQL, no persistent job history database.
- **Why**: Matches the brief's "ephemeral by design" constraint. Simplest viable architecture (Rule 2). Can be revisited if persistence is explicitly requested later.
- **Rejected**: Adding PostgreSQL or SQLite for job history.
- **Rejected Why**: Out of scope for Phase 1; adds a service, migrations, and ORM complexity for no immediate user value.
- **Flagged By**: User
- **Confidence**: High
