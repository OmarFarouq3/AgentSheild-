# Evidence dashboard

Run `python -m frontend.server` from the repository root, then visit
http://127.0.0.1:8787/. No Node/npm build step is required. The dashboard uses
FastAPI (already in the agent dependencies) and locally served HTML/CSS/JS.

The five source artifacts are `baseline_results.json`, `baseline_summary.json`,
`defended_results.json`, `defended_summary.json`, and `comparison_summary.json`
under `results/`. The API recomputes summaries and comparison provenance before
serving them. Missing or stale data yields a visible error rather than demo numbers.
Regenerate comparison with `python -m evaluation.comparison` after a defended run.

Features: overview, matched-ASR charts, category/status/severity filters, side-by-side
response and transcript details, baseline vulnerability cards, coverage exclusions,
remaining risks, evidence hashes, and a two-posture live demo. Live output never
changes historical metrics. Recorded fallback is always available when artifacts
are present, even if Ollama is offline.

Shared routes are also installed in the existing TechPulse FastAPI app at
`/dashboard` when imported with the repository package available. The optional
standalone server avoids starting Postgres just to review JSON. The chat and security suite API endpoints are preserved.

The demo server binds to loopback. Live requests accept only fixed eligible attack
IDs and baseline/defended modes, reject extra fields and cross-origin POSTs, and
run sequentially in isolated subprocesses. Results go to `results/live/<job_id>/`.
Job status is in memory, so restarting the server loses polling IDs but preserves
the result files. Keep this as a local hackathon service; it is not a hosted,
multi-user execution platform. Do not run the CLI and live jobs concurrently on
the same local model if you want stable latency.

Security evidence is escaped as text. No external fonts, CDNs, tracking, image
beacons, or remote scripts are used. All confidential markers shown are synthetic.

Tests:

```powershell
python -m unittest frontend.test_api -v
python -m pip install -r frontend/requirements-test.txt
python -m frontend.test_browser --live
```

The browser test uses installed Microsoft Edge in headless mode, checks responsive
layout and interaction, and saves screenshots under `results/dashboard_*.png`.
Omit `--live` for browser-only checks without calling Ollama.

## Original obeid React console and adaptive red team

The original visual console from `obeid-branch` is in `frontend/src/`. Its two
primary testing pages keep controls, results, and explanations together:

- **Preset evaluation** (`/`): run the fixed attack suite, compare normal and
  defended outcomes, inspect both modes' answers and transcripts, browse the
  preset attack list, and download the report. Results stay available while
  switching pages, but a fresh load starts empty. Download before reloading to
  keep a copy. The older `/results` URL opens this consolidated page too.
- **Adaptive red team** (`/adaptive`): run an offensive campaign driven by prior
  feedback, inspect generated prompts and fallback decisions, compare paired
  results, and download the full evidence. Campaign state survives navigation
  between pages in the current session; reloads clear it from the UI.

Only one test method can run at a time in the console. Their scoring and reports
remain separate. **How defenses work** (`/defenses`) explains the implemented
controls, request flow, posture differences, evidence, and limitations, with
repository references for reviewers. **Agent chat** is a secondary utility. The static
artifact dashboard on port 8787 described above is a separate review tool.

With the backend running on port 8000, use a second PowerShell terminal:

```powershell
cd C:\Users\mahou\AgentSheild-\frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Visit **http://127.0.0.1:5173** and select **Adaptive red team**. Choose two rounds
for a quick check or six to cover all categories and revisit observed gaps.
The Vite `/api` proxy connects to the backend; no CORS changes are needed.
`npm.cmd run build` checks TypeScript and builds the console.

The React console (5173) and artifact dashboard (8787) are separate interfaces.
Docker starts the backend services; start Vite as above for the React console.

Browser regression check (with Vite and backend running):

```powershell
# From the repository root
python -m pip install -r frontend/requirements-test.txt
python -m frontend.test_react_browser
# Also run a real two-round adaptive campaign:
python -m frontend.test_react_browser --live
```

The Vite/React console connects to these backend routes:

- `GET /health`
- `GET /security/attack-cases`
- `POST /security/attack-suite`
- `POST /chat`
- `POST /security/adaptive-suite`

The artifact dashboard described above remains available without the Node toolchain.
