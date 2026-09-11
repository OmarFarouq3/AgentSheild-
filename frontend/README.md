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
standalone server avoids starting Postgres just to review JSON. Existing Chainlit
chat and legacy suite endpoints are preserved.

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

## AI Agent Chat

Start local Ollama with the configured model, then run `python -m frontend.server`
from the repository root (restart an already running server to load the new API).
Open http://127.0.0.1:8787/ and select **AI Agent Chat** in the navigation.
Enter a message, choose **Baseline** or **Defended**, and click **Send**. Each turn
shows the final response, runtime, executed tools and arguments, intercepted
requests, and guard/security events. **Clear chat** removes the visible history.
History is page memory only; every message uses a fresh agent session.

`POST /dashboard-api/chat` accepts only `message` (nonblank, at most 8000
characters) and `security_mode` (`baseline` or `defended`). Baseline maps to the
runtime's `normal` mode. A dedicated subprocess calls
`evaluation.agent_adapter.run_agent`, retaining the existing runtime, dispatcher,
security controls, loopback model restriction, five-tool budget, and synthetic-only
tool isolation. Other tool requests are captured without executing/transmitting.
Requests are serialized, same-origin JSON only, and have a 180-second timeout.
No scoring or report-writing code runs; this playground is excluded from the
official attack-score denominator and never updates historical result files.

## Legacy React console (source)

The repository also retains an older Vite/React console definition in
`package.json` and `src/`. It connects to the existing backend routes:

- `GET /health`
- `GET /security/attack-cases`
- `POST /security/attack-suite`
- `POST /chat`

The current hackathon evidence dashboard described above is the supported local
demo surface and does not require the Node toolchain.
