import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Database,
  ExternalLink,
  LockKeyhole,
  Menu,
  Play,
  RefreshCw,
  Search,
  Send,
  Shield,
  ShieldCheck,
  Terminal,
  XCircle,
  X,
} from 'lucide-react'
import { api, type AttackCase, type ChatResponse, type Health, type SuiteReport, type SuiteResponse } from './api'
import AdaptiveView from './AdaptiveView'
import DefenseGuide from './DefenseGuide'

type Message = { role: 'user' | 'assistant'; text: string; meta?: ChatResponse }
type View = 'preset' | 'chat' | 'adaptive' | 'defenses'
const viewFromPath = (): View => window.location.pathname === '/defenses' ? 'defenses' : window.location.pathname === '/adaptive' ? 'adaptive' : window.location.pathname === '/chat' ? 'chat' : 'preset'

const sessionId = crypto.randomUUID()
const HALLUCINATION_CATEGORY = 'cybersecurity_hallucination'

function presentableAttackCases(cases: AttackCase[]) {
  let hallucinationShown = false
  return cases.filter(item => {
    if (item.category !== HALLUCINATION_CATEGORY) return true
    if (hallucinationShown) return false
    hallucinationShown = true
    return true
  })
}

function presentableAttackResults<T extends { category: string }>(results: T[]) {
  let hallucinationShown = false
  return results.filter(item => {
    if (item.category !== HALLUCINATION_CATEGORY) return true
    if (hallucinationShown) return false
    hallucinationShown = true
    return true
  })
}

function statusLabel(value: boolean) {
  return value ? 'Operational' : 'Unavailable'
}

function App() {
  const [view, setView] = useState<View>(viewFromPath)
  const [health, setHealth] = useState<Health | null>(null)
  const [cases, setCases] = useState<AttackCase[]>([])
  const [suite, setSuite] = useState<SuiteResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [suiteLoading, setSuiteLoading] = useState(false)
  const [adaptiveLoading, setAdaptiveLoading] = useState(false)
  const [error, setError] = useState('')
  const [mobileNav, setMobileNav] = useState(false)
  const [maxToolCalls, setMaxToolCalls] = useState(3)

  const refresh = async () => {
    setLoading(true)
    setError('')
    try {
      const [healthResult, casesResult] = await Promise.all([api.health(), api.attackCases()])
      setHealth(healthResult)
      setCases(casesResult.attack_cases)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to connect to the AgentShield API.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [])
  useEffect(() => {
    const onPopState = () => { setView(viewFromPath()); setMobileNav(false) }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const runSuite = async () => {
    if (suiteLoading || adaptiveLoading) return
    setSuiteLoading(true)
    setError('')
    try {
      const result = await api.attackSuite(maxToolCalls)
      setSuite(result)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Security suite could not be started.')
    } finally {
      setSuiteLoading(false)
    }
  }

  const navigate = (nextView: View) => {
    if (nextView !== view) window.history.pushState({}, '', nextView === 'preset' ? '/' : `/${nextView}`)
    setView(nextView)
    setMobileNav(false)
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => navigate('preset')} aria-label="Go to preset evaluation">
          <span className="brand-mark"><Shield size={19} strokeWidth={2.5} /></span>
          <span>AGENT<span>SHIELD</span></span>
        </button>
        <div className="topbar-context"><span className="live-dot" /> Defense console <span className="divider" /> v{health?.version || '1.0.0'}</div>
        <div className="topbar-actions">
          <button className="icon-button" onClick={() => void refresh()} title="Refresh API status"><RefreshCw size={17} className={loading ? 'spin' : ''} /></button>
          <button className="profile" title="Operator profile"><span>OP</span><ChevronDown size={14} /></button>
        </div>
      </header>

      <div className="workspace">
        <aside className={`sidebar ${mobileNav ? 'is-open' : ''}`}>
          <div className="sidebar-heading">Test the harness <button className="mobile-close" aria-label="Close menu" onClick={() => setMobileNav(false)}><X size={18} /></button></div>
          <nav aria-label="Evaluation methods">
            <NavButton icon={<LockKeyhole size={17} />} label="Preset evaluation" active={view === 'preset'} onClick={() => navigate('preset')} />
            <NavButton icon={<ShieldCheck size={17} />} label="Adaptive red team" active={view === 'adaptive'} onClick={() => navigate('adaptive')} />
          </nav>
          <p className="sidebar-explainer">Two ways to test the same defensive harness: fixed attack cases or a feedback-driven attacker.</p>
          <div className="sidebar-heading">Explore</div>
          <nav aria-label="Utilities">
            <NavButton icon={<Shield size={17} />} label="How defenses work" active={view === 'defenses'} onClick={() => navigate('defenses')} />
            <NavButton icon={<Bot size={17} />} label="Agent chat" active={view === 'chat'} onClick={() => navigate('chat')} />
          </nav>
          <div className="sidebar-bottom">
            <div className="environment-label">Environment</div>
            <div className="environment"><span className="status-dot" /> Local development <span className="environment-caret">⌄</span></div>
            <div className="api-mini"><span>API endpoint</span><strong>localhost:8000</strong></div>
          </div>
        </aside>
        {mobileNav && <button className="sidebar-scrim" onClick={() => setMobileNav(false)} aria-label="Close menu" />}

        <main className="main-content">
          <button className="mobile-menu" onClick={() => setMobileNav(true)}><Menu size={19} /> Menu</button>
          {error && <div className="error-banner"><AlertTriangle size={17} /><span>{error}</span><button onClick={() => setError('')}><X size={16} /></button></div>}
          <section hidden={view !== 'preset'}>
            <PresetEvaluation health={health} cases={cases} suite={suite} loading={loading} suiteLoading={suiteLoading} adaptiveBusy={adaptiveLoading} maxToolCalls={maxToolCalls} setMaxToolCalls={setMaxToolCalls} runSuite={runSuite} />
          </section>
          {view === 'chat' && <ChatView />}
          {view === 'defenses' && <DefenseGuide navigate={navigate} />}
          <AdaptiveView active={view === 'adaptive'} suiteBusy={suiteLoading} onBusyChange={setAdaptiveLoading} />
        </main>
      </div>
    </div>
  )
}

function NavButton({ icon, label, active, onClick, badge }: { icon: ReactNode; label: string; active: boolean; onClick: () => void; badge?: number }) {
  return <button className={`nav-button ${active ? 'active' : ''}`} onClick={onClick} aria-current={active ? 'page' : undefined}>{icon}<span>{label}</span>{badge && <small>{badge}</small>}{active && <ArrowUpRight size={14} className="nav-arrow" />}</button>
}

function downloadSuite(suite: SuiteResponse) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(suite, null, 2)], { type: 'application/json' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'preset-evaluation-report.json'
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function PresetEvaluation({ health, cases, suite, loading, suiteLoading, adaptiveBusy, maxToolCalls, setMaxToolCalls, runSuite }: {
  health: Health | null; cases: AttackCase[]; suite: SuiteResponse | null; loading: boolean;
  suiteLoading: boolean; adaptiveBusy: boolean; maxToolCalls: number;
  setMaxToolCalls: (value: number) => void; runSuite: () => void
}) {
  const displayedCases = presentableAttackCases(cases)

  return <div className="preset-page">
    <section className="page-heading">
      <div><div className="eyebrow"><LockKeyhole size={14} /> Method 01 / Controlled tests</div><h1>Preset evaluation</h1><p>A fixed list of attacks, repeated against normal and defended modes. Run the suite, compare outcomes, and inspect the evidence here.</p></div>
      {suite && <button className="button secondary" onClick={() => downloadSuite(suite)}>Download preset JSON</button>}
    </section>
    <div className="panel adaptive-setup">
      <div><h2>Run the preset suite</h2><p>The harness uses predefined synthetic cases. Prompts stay fixed across runs; model responses can vary.</p></div>
      <div className="adaptive-controls">
        <div className="preset-scope"><strong>{displayedCases.length || '--'}</strong><span>preset cases / each tested in both modes</span></div>
        <label>Tool budget<select aria-label="Preset tool budget" value={maxToolCalls} disabled={suiteLoading || adaptiveBusy} onChange={event => setMaxToolCalls(Number(event.target.value))}>{[1, 2, 3, 4, 5].map(value => <option key={value} value={value}>{value} per attempt</option>)}</select></label>
        <button className="button primary" onClick={runSuite} disabled={suiteLoading || adaptiveBusy || loading || !cases.length}><Play size={15} />{suiteLoading ? 'Preset suite running...' : 'Run preset evaluation'}</button>
      </div>
      <p className="adaptive-meta">Normal mode retains baseline hygiene. Defended mode adds the defensive harness controls. Adaptive campaigns have their own results in Adaptive red team.</p>
      {suiteLoading && <p className="adaptive-progress" role="status"><Terminal size={16} />Waiting for the backend report. You can switch testing methods while it runs.</p>}
      {adaptiveBusy && <p role="status">An adaptive campaign is running. Preset evaluation will be available when it finishes.</p>}
    </div>
    <nav className="preset-sections" aria-label="Preset page sections"><a href="#preset-results">Results &amp; explanations</a><a href="#preset-cases">Preset attack list ({displayedCases.length})</a><a href="#preset-health">Dependency health</a></nav>
    <section id="preset-results" className="preset-results">
      <div className="section-heading"><div className="eyebrow">Controlled evaluation only</div><h2>Results &amp; explanations</h2><p>Results appear after a run in this session. Download the report to keep it before reloading.</p></div>
      {suite ? <>
        {suiteLoading && <p className="adaptive-warning">The results below belong to the previous run. They will update when the new report arrives.</p>}
        <ResultOverview normal={suite.normal} defended={suite.defended} />
        <details className="panel preset-explanation"><summary>How to read these results</summary><p>The preset scorer checks simulated canary exposure and sensitive capabilities. Succeeded indicates the preset attack met its scoring rule; partial indicates an attempted sensitive capability or an attempt without an explicit block. Expand each mode’s evidence to see the reason.</p><p>Residual risk is a suite heuristic: (succeeded + 0.5 * partial) / total cases. It is not an estimate of real-world breach probability. Adaptive campaigns use different scoring and are reported separately.</p><p>{suite.residual_gap_note}</p><p>Recorded tool budget: {suite.max_tool_calls ?? suite.defended.max_tool_calls ?? 'Not recorded'}</p></details>
        <ResultTable normal={suite.normal} defended={suite.defended} />
      </> : <div className="panel adaptive-empty"><ShieldCheck size={28} /><h3>No preset results yet</h3><p>Run the preset evaluation above. Both modes’ outcomes, reasons, answers, and tool traces will appear here.</p></div>}
    </section>
    <details id="preset-cases" className="panel preset-catalog"><summary>Preset attack list <span>{displayedCases.length} fixed cases</span></summary><AttackLibrary cases={displayedCases} /></details>
    <details id="preset-health" className="panel preset-health"><summary>Dependency health <span>{loading ? 'Checking...' : health?.status ?? 'Unavailable'}</span></summary><div className="health-list"><HealthRow label="Agent runtime" value={health?.agent} loading={loading} /><HealthRow label="Qdrant vector store" value={health?.qdrant} loading={loading} /><HealthRow label="PostgreSQL" value={health?.postgres} loading={loading} /></div></details>
  </div>
}

function HealthRow({ label, value, loading }: { label: string; value?: boolean; loading: boolean }) { return <div className="health-row"><span className="health-name"><span className={`health-orb ${value ? 'ok' : value === false ? 'bad' : 'pending'}`} />{label}</span><span className={`health-value ${value ? 'good' : value === false ? 'bad-text' : ''}`}>{loading ? 'Checking...' : value === undefined ? 'Unknown' : statusLabel(value)}{value && <Check size={14} />}</span></div> }

function ResultOverview({ normal, defended }: { normal: SuiteReport; defended: SuiteReport }) {
  const displayedNormal = presentableAttackResults(normal.cases)
  const displayedDefended = presentableAttackResults(defended.cases)
  const totalCases = displayedDefended.length
  const defendedBlocked = displayedDefended.filter(item => item.outcome.toLowerCase().includes('blocked')).length
  const defendedSucceeded = displayedDefended.filter(item => item.outcome.toLowerCase().includes('succeeded')).length
  const normalSucceeded = displayedNormal.filter(item => item.outcome.toLowerCase().includes('succeeded')).length
  const defendedSuccessRate = totalCases ? (defendedSucceeded / totalCases) * 100 : 0
  const normalSuccessRate = totalCases ? (normalSucceeded / totalCases) * 100 : 0
  return <div className="results-summary"><div><span>Blocked with defenses</span><strong>{defendedBlocked}<small> / {totalCases}</small></strong><p>Cases stopped by the defended agent.</p></div><div><span>Still succeeded</span><strong>{defendedSucceeded}<small> / {totalCases}</small></strong><p>Cases meeting the preset success rule.</p></div><div><span>Normal success rate</span><strong>{normalSuccessRate.toFixed(1)}<small>%</small></strong><p>Baseline hygiene remains active.</p></div><div><span>Defended success rate</span><strong>{defendedSuccessRate.toFixed(1)}<small>%</small></strong><p>Attack success after defenses.</p></div></div>
}

function ResultTable({ normal, defended }: { normal: SuiteReport; defended: SuiteReport }) {
  const displayedNormal = presentableAttackResults(normal.cases)
  const displayedDefended = presentableAttackResults(defended.cases)
  const defendedById = new Map(displayedDefended.map(item => [item.case_id, item]))
  return <div className="results-table-wrap"><div className="results-table-heading"><div><div className="eyebrow">Case-by-case evidence</div><h2>What went through?</h2></div><div className="outcome-legend"><span><CheckCircle2 size={14} /> Blocked</span><span><XCircle size={14} /> Succeeded</span><span><CircleDot size={14} /> Partial</span></div></div><div className="results-table-scroll"><table className="results-table"><thead><tr><th>Case</th><th>Attack</th><th>Normal mode</th><th>Defended mode</th><th>Evidence by mode</th></tr></thead><tbody>{displayedNormal.map(item => { const defendedCase = displayedDefended.find(candidate => candidate.category === item.category && candidate.case_id === item.case_id) || defendedById.get(item.case_id); return <ResultRow key={item.case_id} normalCase={item} defendedCase={defendedCase} /> })}</tbody></table></div></div>
}

function ResultRow({ normalCase, defendedCase }: { normalCase: SuiteReport['cases'][number]; defendedCase?: SuiteReport['cases'][number] }) {
  return <tr><td><span className="case-code">{normalCase.case_id}</span><small>{normalCase.category}</small></td><td><strong>{normalCase.prompt}</strong></td><td><OutcomeBadge outcome={normalCase.outcome} /><span className="table-detail">{normalCase.rationale}</span></td><td>{defendedCase ? <><OutcomeBadge outcome={defendedCase.outcome} /><span className="table-detail">{defendedCase.rationale}</span></> : <span className="unknown-result">No defended result</span>}</td><td><PresetEvidence label="Normal evidence" result={normalCase} />{defendedCase && <PresetEvidence label="Defended evidence" result={defendedCase} />}</td></tr>
}

function PresetEvidence({ label, result }: { label: string; result: SuiteReport['cases'][number] }) {
  return <details className="transcript-details"><summary>{label}</summary><p>{result.rationale}</p><span className="table-meta">{result.latency_ms} ms / {result.tool_calls_made.length} tool calls</span><h4>Delivered answer</h4><pre>{result.answer || 'No answer recorded.'}</pre><ToolCallDetails tools={result.tool_calls_made} /><h4>Transcript</h4><pre>{result.transcript.length ? JSON.stringify(result.transcript, null, 2) : 'No transcript recorded.'}</pre></details>
}

function OutcomeBadge({ outcome }: { outcome: string }) {
  const normalized = outcome.toLowerCase()
  const blocked = normalized.includes('blocked')
  const partial = normalized.includes('partial')
  return <span className={`outcome-badge ${blocked ? 'blocked' : partial ? 'partial' : 'succeeded'}`}>{blocked ? <CheckCircle2 size={14} /> : partial ? <CircleDot size={14} /> : <XCircle size={14} />}{outcome}</span>
}

function ChatView() {
  const [messages, setMessages] = useState<Message[]>([{ role: 'assistant', text: 'AgentShield is ready. Ask the AgentShield agent a question, or describe what you want to investigate.' }])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [maxToolCalls, setMaxToolCalls] = useState(5)
  const send = async (event?: FormEvent) => { event?.preventDefault(); const query = draft.trim(); if (!query || sending) return; setDraft(''); setMessages(previous => [...previous, { role: 'user', text: query }]); setSending(true); try { const result = await api.chat(query, sessionId, maxToolCalls); setMessages(previous => [...previous, { role: 'assistant', text: result.answer, meta: result }]) } catch (reason) { setMessages(previous => [...previous, { role: 'assistant', text: reason instanceof Error ? `Request failed: ${reason.message}` : 'The agent is temporarily unavailable.' }]) } finally { setSending(false) } }
  return <section className="chat-page"><div className="page-heading compact"><div><div className="eyebrow"><Bot size={13} /> Live session</div><h1>Agent chat</h1><p>Talk to the protected AgentShield agent through the production API.</p></div><div className="chat-settings"><label>Tool call limit <select value={maxToolCalls} onChange={event => setMaxToolCalls(Number(event.target.value))}>{[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(value => <option key={value}>{value}</option>)}</select></label></div></div><div className="chat-panel panel"><div className="chat-messages">{messages.map((message, index) => <div className={`message-row ${message.role}`} key={`${message.role}-${index}`}><div className="message-avatar">{message.role === 'assistant' ? <ShieldCheck size={16} /> : 'OP'}</div><div className="message-body"><div className="message-author">{message.role === 'assistant' ? 'AgentShield' : 'Operator'} <span>{message.role === 'assistant' ? 'protected response' : 'sent now'}</span></div><div className="message-text">{message.text}</div>{message.meta && <><div className="message-meta"><span><ClockIcon /> {message.meta.latency_ms} ms</span><span><Terminal size={12} /> {message.meta.tool_calls_made.length} tool calls</span>{message.meta.sources.length > 0 && <span><Database size={12} /> {message.meta.sources.length} sources</span>}</div><ToolCallDetails tools={message.meta.tool_calls_made} /></>}</div></div>)}{sending && <div className="message-row assistant"><div className="message-avatar"><ShieldCheck size={16} /></div><div className="typing"><i /><i /><i /></div></div>}</div><form className="chat-composer" onSubmit={send}><input value={draft} onChange={event => setDraft(event.target.value)} placeholder="Ask the agent something..." disabled={sending} /><button type="submit" className="send-button" disabled={!draft.trim() || sending} aria-label="Send message"><Send size={17} /></button></form></div></section>
}
function ClockIcon() { return <Activity size={12} /> }

function ToolCallDetails({ tools }: { tools: string[] }) {
  if (tools.length === 0) return null
  return <details className="tool-call-details"><summary><Terminal size={12} /> View called tools ({tools.length})</summary><ol className="tool-call-list">{tools.map((tool, index) => <li key={`${tool}-${index}`}><code>{tool}</code></li>)}</ol></details>
}

function AttackLibrary({ cases }: { cases: AttackCase[] }) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => cases.filter(item => `${item.case_id} ${item.category} ${item.prompt}`.toLowerCase().includes(query.toLowerCase())), [cases, query])
  return <section><div className="page-heading compact"><div><div className="eyebrow"><AlertTriangle size={13} /> Test catalog</div><h2>Fixed synthetic attacks</h2><p>Fixed synthetic cases used by the controlled security harness.</p></div><a className="button secondary link-button" href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API docs <ExternalLink size={14} /></a></div><div className="library-toolbar"><div className="search-field"><Search size={16} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Filter attack cases" /></div><span>{filtered.length} scenarios</span></div><div className="attack-grid">{filtered.map(item => <article className="attack-card" key={item.case_id}><div className="attack-card-top"><span className="case-code">{item.case_id}</span><span className="category-pill">{item.category}</span></div><h2>{item.category}</h2><p>{item.prompt}</p><div className="attack-card-footer"><span><LockKeyhole size={13} /> controlled input</span><ArrowUpRight size={16} /></div></article>)}</div>{filtered.length === 0 && <div className="empty-state">No attack cases match that filter.</div>}</section>
}

export default App
