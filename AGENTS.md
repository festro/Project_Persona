# AGENTS.md -- Project_Persona

See `D:\Projects\AGENTS.md` for the cross-project agent operating notes this repo
follows (the sandbox mount is not authoritative -> validate at the Windows source;
git runs Windows-side; live validation runs on the Windows host; Pacific timestamps
+ imperial units per `WORKFLOW.md`).

Last updated: 2026-06-07 1135 PT by Claude. Keep ASCII.

## Project-local additions

- Entry point: `manage.py` -- cross-platform, pure-stdlib launcher (up / down /
  toggle / status / doctor / capabilities / test / panel). Invoke with the bundled
  interpreter `portable\python\python.exe` (3.11.9). Shims: `start-stop.bat/.sh`,
  `test.bat/.sh`, `windows_portable_run.bat`.
- Live stack: llama-server on `:8090`, FastAPI companion API on `:8000`.
- `manage.py` cannot be parsed/validated through the sandbox mount (truncated
  reads); AST-check a completeness-verified off-mount copy, and run the live
  `up/down/status/doctor/capabilities/test` on the Windows host.
