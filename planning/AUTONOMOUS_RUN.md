# Autonomous Run — mandate (2026-06-25 → user away ~2 days)

The user (Carlos) is away ~2 days and authorized completing the **entire project**
end-to-end autonomously. This file is the standing mandate + my operating protocol.
It is also the record so the user can audit what I was told and how I worked.

## Mandate (user's words, paraphrased)
- Complete the whole project from start to finish, integrally.
- Drive execution with `promptloop.sh`, and launch `/goal` myself when useful.
- **After each phase: run `/checkpoint` and push to GitHub.**
- Any issue/decision NOT covered by the blueprint is at **my discretion** — but it must
  be **justified and documented** (user won't be available for design decisions).
- When everything is done: launch a loop to verify the whole project follows the
  project guidelines, and review the generated reports for possible improvements.
- **When ALL is finished and pushed: shut down the WHOLE Windows PC** — not just WSL.
  From WSL that means `/mnt/c/Windows/System32/shutdown.exe /s /t 0` (verified reachable),
  NOT `wsl --shutdown`.

## Operating protocol
1. Build phase by phase per `planning/PLAN.md` / the blueprint anchor.
2. Verification gate before closing a phase: `pytest -q`, `ruff check .`, `mypy src/`.
3. `/checkpoint` + `git push` at the end of every phase.
4. Every off-blueprint decision → logged in `planning/DECISIONS.md` (with rationale)
   and in the day's bitácora.
5. Final: a verification loop over guidelines + a report-improvement review.
6. **Last action of the entire run: shut down the Windows host.**

## Known environment facts (this machine)
- GPU: RTX 4080 (16 GB VRAM) · 448 GB free · 29 GB RAM · WSL on Windows.
- Python venv at `.venv` (numpy, lasio installed; more added per phase).
- Ollama NOT yet installed — needed for Phases 5-6 (LLM agents). Install attempts via
  the public tgz URLs 404'd; resolve with a working method (e.g. `ollama.com/install.sh`
  or the correct GitHub release asset) when reaching Phase 5. Models: qwen3:30b-a3b
  (writer, quantized for 16 GB), llama3.1:8b (adversarial reviewer).
- VOLVE data (Phase 8 regression) must be sourced; document if unavailable.

## Do NOT shut down until
- All phases that are achievable are complete (or honestly documented as blocked),
- everything is committed AND pushed to GitHub,
- the final verification loop + report review are done and recorded.
