# Gemini2API Handoff Package

Created: 2026-06-13

This folder is the portable handoff bundle for the next AI/operator. It keeps the codebase state, binary artifacts, launch helpers, and sanitized real-test evidence in one Git-tracked place.

## Start Here

- Main handoff notes: `handoff/AI_HANDOFF_2026-06-13.md`
- Change snapshot: `handoff/CHANGELOG_SNAPSHOT_2026-06-13.md`
- Sanitized live evidence: `handoff/evidence/`
- Native Windows release artifacts: `handoff/artifacts/native-x64-release/`
- Launch script copies: `handoff/scripts/`

## Current Known Good Commands

```powershell
python -m pytest
python -m gemini_web2api
```

Service defaults:

- API base: `http://localhost:8081/v1`
- Dashboard: `http://localhost:8081/dashboard`
- Google-compatible base: `http://localhost:8081`

## Important Notes

- Do not flatten this repository back to upstream. The local repository intentionally contains many extra features not present in `Sophomoresty/gemini-web2api`.
- Keep credentials out of future commits. The evidence files in this folder are sanitized.
- The native EXE and runtime side files are copied into `handoff/artifacts/native-x64-release/` because `build/` is intentionally ignored.
- Real media generation endpoints are present but still need deeper upstream RPC/browser work before they can be called fully supported.
