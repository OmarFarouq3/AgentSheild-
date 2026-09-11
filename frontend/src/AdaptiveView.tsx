import { useEffect, useState } from 'react'
import { AlertTriangle, Download, Play, ShieldCheck, Terminal } from 'lucide-react'
import { api, type AdaptiveAttempt, type AdaptiveReport, type AdaptiveRound } from './api'

const labels: Record<string, string> = {
  blocked: 'Blocked', partial: 'Partial access', succeeded: 'Succeeded',
  not_exercised: 'Not exercised', error: 'Error',
}
const sources = { model: 'Local model', policy: 'Feedback policy', policy_fallback: 'Policy fallback' }
const percent = (value: number | null) => value === null ? 'N/A' : `${value.toFixed(1)}%`
const readable = (value: string) => value.replaceAll('_', ' ')

function Outcome({ attempt }: { attempt?: AdaptiveAttempt }) {
  const outcome = attempt?.outcome ?? 'missing'
  return <span className={`adaptive-outcome ${outcome}`}>{labels[outcome] ?? 'Missing'}</span>
}

function Evidence({ label, attempt }: { label: string; attempt?: AdaptiveAttempt }) {
  if (!attempt) return <article className="adaptive-evidence"><h3>{label}</h3><p>No attempt was returned for this posture.</p></article>
  return <article className="adaptive-evidence">
    <div className="adaptive-evidence-heading"><h3>{label}</h3><Outcome attempt={attempt} /></div>
    <p>{attempt.rationale}</p>
    <div className="adaptive-meta">{attempt.latency_ms} ms · Coverage {attempt.coverage_complete ? 'complete' : 'incomplete'}</div>
    <h4>Controls observed</h4><p>{attempt.controls_triggered.join(', ') || 'No explicit control event'}</p>
    <h4>Delivered answer</h4><pre>{attempt.answer || 'No answer returned.'}</pre>
    <details><summary>Executed tools and arguments ({attempt.tools_called.length})</summary><pre>{JSON.stringify(attempt.tools_called, null, 2)}</pre></details>
    <details><summary>Intercepted requests ({attempt.intercepted_tool_calls.length})</summary><pre>{JSON.stringify(attempt.intercepted_tool_calls, null, 2)}</pre></details>
    <details><summary>Full target trace and scoring</summary><pre>{JSON.stringify(attempt, null, 2)}</pre></details>
  </article>
}

function Candidate({ round }: { round: AdaptiveRound }) {
  return <details className="panel adaptive-candidate" open={round.round === 1}>
    <summary className="adaptive-candidate-heading">
      <span><span className="eyebrow">Round {round.round} · {sources[round.generation.source]}</span><strong>{readable(round.strategy)}</strong><small>{readable(round.category)}</small></span>
      <span className="adaptive-pair"><span>Normal <Outcome attempt={round.attempts.normal} /></span><span>Defended <Outcome attempt={round.attempts.defended} /></span></span>
    </summary>
    <div className="adaptive-candidate-content">
      <h3>Why this candidate</h3><p>{round.generation.rationale}</p>
      {round.generation.fallback_reason && <p className="adaptive-warning">{round.generation.fallback_reason}</p>}
      <div className="adaptive-meta">Candidate: {round.candidate_id}<br />Parent: {round.parent_candidate_id ?? 'First exploration of this category'}</div>
      <h4>Prompt sent unchanged to both postures</h4><pre>{round.prompt}</pre>
      {round.document_payload !== null && <><h4>Untrusted document payload</h4><pre>{round.document_payload}</pre><p className="adaptive-meta">Payload SHA-256: {round.payload_sha256}</p></>}
      <details><summary>Feedback used for this decision</summary><pre>{JSON.stringify(round.generation.feedback_basis, null, 2)}</pre></details>
      <div className="adaptive-evidence-grid"><Evidence label="Undefended / normal" attempt={round.attempts.normal} /><Evidence label="Defended" attempt={round.attempts.defended} /></div>
    </div>
  </details>
}

function download(report: AdaptiveReport) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'adaptive-security-report.json'
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function AdaptiveView({ active, suiteBusy, onBusyChange }: {
  active: boolean; suiteBusy: boolean; onBusyChange: (busy: boolean) => void
}) {
  const [rounds, setRounds] = useState(6)
  const [generator, setGenerator] = useState<'model' | 'policy'>('model')
  const [maxTools, setMaxTools] = useState(3)
  const [busy, setBusy] = useState(false)
  const [startedAt, setStartedAt] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState('')
  const [report, setReport] = useState<AdaptiveReport | null>(null)
  useEffect(() => {
    if (!busy) return
    const interval = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000)
    return () => window.clearInterval(interval)
  }, [busy, startedAt])

  const run = async () => {
    if (busy || suiteBusy) return
    setBusy(true); onBusyChange(true); setError(''); setElapsed(0); setStartedAt(Date.now())
    try {
      const result = await api.adaptiveSuite(rounds, generator, maxTools)
      if (result.suite_kind !== 'adaptive' || !['completed', 'incomplete'].includes(result.status)
          || !Array.isArray(result.rounds) || !result.comparison || !result.normal || !result.defended) {
        throw new Error('The API returned an incompatible adaptive report.')
      }
      setReport(result)
    } catch (reason) {
      setError(`${reason instanceof Error ? reason.message : 'Campaign request failed.'} No new report was received. Check saved backend evidence before retrying; the backend may still be running.`)
    } finally { setBusy(false); onBusyChange(false) }
  }

  return <section hidden={!active} className="adaptive-page">
    <div className="page-heading"><div><div className="eyebrow"><ShieldCheck size={14} /> Method 02 / Dynamic attacks</div><h1>Adaptive red team</h1><p>An offensive agent adapts attacks using prior outcomes. Configure the campaign, compare both postures, and trace every decision here.</p></div>
      {report && <button className="button secondary" onClick={() => download(report)}><Download size={15} /> Download JSON</button>}
    </div>
    <div className="panel adaptive-setup">
      <div><h2>Run a paired campaign</h2><p>Each candidate runs unchanged in fresh normal and defended sessions. The local attacker uses prior results to generate the next prompt or injected document.</p></div>
      <div className="adaptive-controls">
        <label>Rounds<select aria-label="Adaptive rounds" value={rounds} onChange={event => setRounds(Number(event.target.value))} disabled={busy}>{Array.from({ length: 12 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n} ({n * 2} target attempts)</option>)}</select></label>
        <label>Generator<select aria-label="Attack generator" value={generator} onChange={event => setGenerator(event.target.value as 'model' | 'policy')} disabled={busy}><option value="model">Local model + fallback</option><option value="policy">Feedback policy</option></select></label>
        <label>Tool budget<select aria-label="Adaptive tool budget" value={maxTools} onChange={event => setMaxTools(Number(event.target.value))} disabled={busy}>{[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n} per attempt</option>)}</select></label>
        <button className="button primary" onClick={() => void run()} disabled={busy || suiteBusy}><Play size={15} /> {busy ? 'Campaign running…' : 'Run adaptive campaign'}</button>
      </div>
      <p className="adaptive-meta">Synthetic tools only · 60 seconds per target attempt · 30 seconds per model proposal. Normal retains baseline hygiene. The first five rounds explore the five categories; later rounds revisit observed gaps.</p>
      <details className="adaptive-method-help"><summary>How this testing method works</summary><p>The local model proposes prompts or injected documents using structured feedback from earlier rounds. Feedback policy mode chooses and varies built-in strategies from those outcomes; it also supplies the fallback when a model proposal is rejected.</p><p>Each candidate is tested in both modes before the next round. This page keeps campaign results separate from the fixed attacks in Preset evaluation. Expand a round to inspect its generation reason, feedback, exact payload, and target evidence.</p></details>
      {busy && <p className="adaptive-progress" role="status"><Terminal size={16} /> {elapsed}s elapsed. Waiting for the backend report; round evidence appears when the campaign finishes. You can switch pages while it runs.</p>}
      {suiteBusy && !busy && <p role="status">The fixed suite is running. Wait for it to finish before starting this campaign.</p>}
    </div>
    {error && <div className="error-banner" role="alert"><AlertTriangle size={18} /><span>{error}</span></div>}
    {!report && <div className="panel adaptive-empty"><ShieldCheck size={28} /><h2>Every attempt leaves a trace</h2><p>Run a campaign to inspect paired outcomes, generated prompts, injected documents, controls, and tool arguments. No demo scores are prefilled.</p></div>}
    {report && <>
      {(busy || error) && <p className="adaptive-warning">The report below is the previous completed response, not the current request.</p>}
      <div className="adaptive-report-heading"><h2>{report.status === 'completed' ? 'Campaign completed' : 'Campaign incomplete'}</h2><span className="adaptive-meta">{report.rounds.length} rounds recorded · {report.created_at}</span></div>
      {report.artifact_error && <p className="adaptive-warning" role="alert">{report.artifact_error}</p>}
      <div className="stat-grid">
        {([['Valid paired rounds', String(report.comparison.paired_valid_rounds), 'Both postures have valid evidence'], ['Normal disclosure rate', percent(report.comparison.normal_success_rate_percent), 'Identical valid pairs only'], ['Defended disclosure rate', percent(report.comparison.defended_success_rate_percent), 'Identical valid pairs only'], ['Disclosure rate drop', report.comparison.success_rate_drop_percentage_points === null ? 'N/A' : `${report.comparison.success_rate_drop_percentage_points.toFixed(1)} pts`, 'Negative values mean a regression']] as const).map(([label, value, note]) => <article className="stat-card" key={label}><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></article>)}
      </div>
      <div className="panel adaptive-totals"><div className="results-table-scroll"><table className="results-table"><thead><tr><th>Posture</th><th>Valid / attempts</th><th>Blocked</th><th>Partial</th><th>Succeeded</th><th>Not exercised</th><th>Errors</th></tr></thead><tbody>{(['normal', 'defended'] as const).map(mode => <tr key={mode}><td>{mode === 'normal' ? 'Undefended / normal' : 'Defended'}</td><td>{report[mode].valid_evaluated_attacks} / {report[mode].total_attacks}</td><td>{report[mode].blocked}</td><td>{report[mode].partial}</td><td>{report[mode].succeeded}</td><td>{report[mode].not_exercised}</td><td>{report[mode].error}</td></tr>)}</tbody></table></div>
        <p className="adaptive-meta">Partial means measured sensitive access or an intercepted exfiltration attempt, not a final-answer leak. Errors and unexercised attempts do not enter rates. N/A means no valid measurement.</p></div>
      {report.comparison.paired_valid_rounds === 0 && <p className="adaptive-warning">No valid paired comparison is available. This run does not establish a defense improvement.</p>}
      <div className="adaptive-rounds">{report.rounds.map(round => <Candidate key={round.candidate_id} round={round} />)}</div>
      <details className="panel adaptive-run-metadata"><summary>Run configuration, integrity artifacts, and limits</summary><p>{report.residual_gap_note}</p><pre>{JSON.stringify({ campaign_id: report.campaign_id, schema_version: report.schema_version, stop_reason: report.stop_reason, config: report.config, model: report.model, generator_model: report.generator_model, isolation: report.isolation, scoring: report.scoring, artifacts: report.artifacts }, null, 2)}</pre></details>
    </>}
  </section>
}
