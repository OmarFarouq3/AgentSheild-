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
  FileText,
  Gauge,
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

type Message = { role: 'user' | 'assistant'; text: string; meta?: ChatResponse }
type View = 'overview' | 'chat' | 'attacks' | 'results'

const sessionId = crypto.randomUUID()

function readStoredSuite(): SuiteResponse | null {
  const stored = localStorage.getItem('agentshield-latest-suite')
  if (!stored) return null
  try {
    return JSON.parse(stored) as SuiteResponse
  } catch {
    localStorage.removeItem('agentshield-latest-suite')
    return null
  }
}

function statusLabel(value: boolean) {
  return value ? 'Operational' : 'Unavailable'
}

function App() {
  const [view, setView] = useState<View>(window.location.pathname === '/results' ? 'results' : 'overview')
  const [health, setHealth] = useState<Health | null>(null)
  const [cases, setCases] = useState<AttackCase[]>([])
  const [suite, setSuite] = useState<SuiteResponse | null>(() => readStoredSuite())
  const [loading, setLoading] = useState(true)
  const [suiteLoading, setSuiteLoading] = useState(false)
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

  const runSuite = async () => {
    setSuiteLoading(true)
    setError('')
    try {
      const result = await api.attackSuite(maxToolCalls)
      setSuite(result)
      localStorage.setItem('agentshield-latest-suite', JSON.stringify(result))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Security suite could not be started.')
    } finally {
      setSuiteLoading(false)
    }
  }

  const navigate = (nextView: View) => {
    setView(nextView)
    setMobileNav(false)
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => navigate('overview')} aria-label="Go to overview">
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
          <div className="sidebar-heading">Workspace <button className="mobile-close" onClick={() => setMobileNav(false)}><X size={18} /></button></div>
          <nav>
            <NavButton icon={<Gauge size={17} />} label="Overview" active={view === 'overview'} onClick={() => navigate('overview')} />
            <NavButton icon={<Bot size={17} />} label="Agent chat" active={view === 'chat'} onClick={() => navigate('chat')} />
            <NavButton icon={<AlertTriangle size={17} />} label="Attack library" active={view === 'attacks'} onClick={() => navigate('attacks')} badge={cases.length || undefined} />
            <NavButton icon={<FileText size={17} />} label="Suite results" active={view === 'results'} onClick={() => navigate('results')} />
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
          {view === 'overview' && <Overview health={health} cases={cases} suite={suite} loading={loading} suiteLoading={suiteLoading} maxToolCalls={maxToolCalls} setMaxToolCalls={setMaxToolCalls} runSuite={runSuite} navigate={navigate} />}
          {view === 'chat' && <ChatView />}
          {view === 'attacks' && <AttackLibrary cases={cases} />}
          {view === 'results' && <ResultsPage />}
        </main>
      </div>
    </div>
  )
}

function NavButton({ icon, label, active, onClick, badge }: { icon: ReactNode; label: string; active: boolean; onClick: () => void; badge?: number }) {
  return <button className={`nav-button ${active ? 'active' : ''}`} onClick={onClick}>{icon}<span>{label}</span>{badge && <small>{badge}</small>}{active && <ArrowUpRight size={14} className="nav-arrow" />}</button>
}

function Overview({ health, cases, suite, loading, suiteLoading, maxToolCalls, setMaxToolCalls, runSuite, navigate }: { health: Health | null; cases: AttackCase[]; suite: SuiteResponse | null; loading: boolean; suiteLoading: boolean; maxToolCalls: number; setMaxToolCalls: (value: number) => void; runSuite: () => void; navigate: (view: View) => void }) {
  const defended = suite?.defended
  const normal = suite?.normal
  const defenseLift = suite?.residual_risk_drop_percentage_points ?? (normal && defended ? normal.residual_risk_score_percent - defended.residual_risk_score_percent : null)
  return <>
    <section className="page-heading">
      <div><div className="eyebrow"><CircleDot size={13} /> Control room</div><h1>Security posture</h1><p>Monitor your agent, validate defenses, and investigate attack behavior.</p></div>
      <div className="heading-actions"><button className="button secondary" onClick={() => navigate('chat')}><Bot size={16} /> Open agent chat</button><button className="button primary" onClick={runSuite} disabled={suiteLoading}><Play size={15} fill="currentColor" /> {suiteLoading ? 'Running suite...' : 'Run security suite'}</button></div>
    </section>
    <section className="stat-grid">
      <StatCard label="Residual risk reduction" value={defenseLift !== null ? `${Math.max(0, defenseLift).toFixed(1)} pts` : '--'} note={defenseLift !== null ? 'lower risk with defenses on' : 'run a suite to measure'} icon={<ShieldCheck />} accent="green" />
      <StatCard label="Attack scenarios" value={cases.length ? String(cases.length).padStart(2, '0') : '--'} note="synthetic test cases loaded" icon={<AlertTriangle />} accent="amber" />
      <StatCard label="Agent health" value={health?.status === 'healthy' ? 'Healthy' : health ? 'Degraded' : '--'} note={health ? 'all critical dependencies' : 'checking backend'} icon={<Activity />} accent={health?.status === 'healthy' ? 'green' : 'red'} />
      <StatCard label="Latest run" value={suite ? `${suite.defended.blocked}/${suite.defended.total_attacks}` : '--'} note={suite ? 'attacks blocked after defense' : 'no run recorded'} icon={<Terminal />} accent="blue" />
    </section>
    <section className="content-grid">
      <div className="panel health-panel"><PanelHeader eyebrow="System status" title="Dependency health" action={<button className="text-button" onClick={() => window.location.reload()}>Refresh <RefreshCw size={13} /></button>} />
        <div className="health-list"><HealthRow label="Agent runtime" value={health?.agent} loading={loading} /><HealthRow label="Qdrant vector store" value={health?.qdrant} loading={loading} /><HealthRow label="PostgreSQL" value={health?.postgres} loading={loading} /></div>
        <div className="panel-footer"><span>Last checked {loading ? 'now' : 'just now'}</span><span className={`request-state ${health ? '' : 'bad-text'}`}><span className="status-dot" /> {health ? 'API connected' : 'API unavailable'}</span></div>
      </div>
      <div className="panel suite-panel"><PanelHeader eyebrow="Controlled evaluation" title="Before vs. after defense" action={<LockKeyhole size={18} className="muted-icon" />} />
        {!suite ? <div className="empty-suite"><div className="empty-icon"><ShieldCheck size={22} /></div><strong>Measure your current posture</strong><p>Run the fixed attack suite to compare the agent in normal and defended modes.</p><div className="run-controls"><label>Max tool calls <select value={maxToolCalls} onChange={(event) => setMaxToolCalls(Number(event.target.value))}>{[1, 2, 3, 4, 5].map(value => <option key={value}>{value}</option>)}</select></label><button className="button dark" onClick={runSuite} disabled={suiteLoading}><Play size={14} fill="currentColor" /> Run test</button></div></div> : <SuiteSummary suite={suite} />}
      </div>
    </section>
    <section className="panel cases-panel"><PanelHeader eyebrow="Attack library" title="What are we testing?" action={<button className="text-button" onClick={() => navigate('attacks')}>View all <ArrowUpRight size={14} /></button>} /><div className="case-strip">{cases.slice(0, 4).map(item => <div className="case-chip" key={item.case_id}><span className="case-code">{item.case_id}</span><strong>{item.category}</strong><p>{item.prompt}</p></div>)}</div></section>
  </>
}

function StatCard({ label, value, note, icon, accent }: { label: string; value: string; note: string; icon: ReactNode; accent: string }) {
  return <div className="stat-card"><div className={`stat-icon ${accent}`}>{icon}</div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></div>
}

function PanelHeader({ eyebrow, title, action }: { eyebrow: string; title: string; action?: ReactNode }) { return <div className="panel-header"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2></div>{action}</div> }
function HealthRow({ label, value, loading }: { label: string; value?: boolean; loading: boolean }) { return <div className="health-row"><span className="health-name"><span className={`health-orb ${value ? 'ok' : value === false ? 'bad' : 'pending'}`} />{label}</span><span className={`health-value ${value ? 'good' : value === false ? 'bad-text' : ''}`}>{loading ? 'Checking...' : value === undefined ? 'Unknown' : statusLabel(value)}{value && <Check size={14} />}</span></div> }

function SuiteSummary({ suite }: { suite: SuiteResponse }) {
  const { normal, defended } = suite
  const reduction = suite.residual_risk_drop_percentage_points ?? normal.residual_risk_score_percent - defended.residual_risk_score_percent
  return <div className="suite-results"><div className="result-hero"><div><span className="result-label">Residual risk after defenses</span><strong>{defended.residual_risk_score_percent.toFixed(1)}<small>%</small></strong><span className="result-explainer">Estimated share of attack pressure still getting through.</span></div><div className="reduction"><ArrowUpRight size={16} /> {Math.max(0, reduction).toFixed(1)} pts<br /><span>lower risk than normal</span></div></div><div className="comparison"><div><span>Without defenses: attacks getting through</span><strong>{normal.attack_success_rate_percent.toFixed(1)}%</strong><div className="bar"><i style={{ width: `${normal.attack_success_rate_percent}%` }} /></div></div><div><span>With defenses: attacks getting through</span><strong>{defended.attack_success_rate_percent.toFixed(1)}%</strong><div className="bar defended"><i style={{ width: `${defended.attack_success_rate_percent}%` }} /></div></div></div><div className="suite-foot"><span><ShieldCheck size={15} /> {defended.blocked} of {defended.total_attacks} blocked</span><button className="text-button" onClick={() => window.open('/results', '_blank', 'noopener,noreferrer')}>See every attack <ExternalLink size={13} /></button></div></div>
}

function ResultsPage() {
  const [suite, setSuite] = useState<SuiteResponse | null>(null)
  useEffect(() => {
    const stored = localStorage.getItem('agentshield-latest-suite')
    if (stored) {
      try { setSuite(JSON.parse(stored) as SuiteResponse) } catch { localStorage.removeItem('agentshield-latest-suite') }
    }
  }, [])

  if (!suite) return <section><div className="page-heading compact"><div><div className="eyebrow"><Terminal size={13} /> Evidence report</div><h1>Suite results</h1><p>Run the security suite from the overview first. The latest report will appear here.</p></div></div><div className="empty-state"><div className="empty-icon"><ShieldCheck size={22} /></div><strong>No suite report yet</strong><p>Return to the overview and run a controlled evaluation.</p></div></section>
  return <section className="results-page"><div className="page-heading compact"><div><div className="eyebrow"><Terminal size={13} /> Evidence report</div><h1>Attack results</h1><p>Every test case, outcome, and reason from the latest normal-versus-defended run.</p></div><div className="report-meta"><span>Max tool calls: {suite.defended.max_tool_calls}</span><span>Scenarios: {suite.defended.total_attacks}</span></div></div><ResultOverview normal={suite.normal} defended={suite.defended} /><ResultTable normal={suite.normal} defended={suite.defended} /></section>
}

function ResultOverview({ normal, defended }: { normal: SuiteReport; defended: SuiteReport }) {
  return <div className="results-summary"><div><span>Blocked with defenses</span><strong>{defended.blocked}<small> / {defended.total_attacks}</small></strong><p>Cases stopped by the defended agent.</p></div><div><span>Still succeeded</span><strong>{defended.succeeded}<small> / {defended.total_attacks}</small></strong><p>Cases where the attack achieved its goal.</p></div><div><span>Normal success rate</span><strong>{normal.attack_success_rate_percent.toFixed(1)}<small>%</small></strong><p>Baseline without defenses.</p></div><div><span>Defended success rate</span><strong>{defended.attack_success_rate_percent.toFixed(1)}<small>%</small></strong><p>Attack success after defenses.</p></div></div>
}

function ResultTable({ normal, defended }: { normal: SuiteReport; defended: SuiteReport }) {
  const defendedById = new Map(defended.cases.map(item => [item.case_id, item]))
  return <div className="results-table-wrap"><div className="results-table-heading"><div><div className="eyebrow">Case-by-case evidence</div><h2>What went through?</h2></div><div className="outcome-legend"><span><CheckCircle2 size={14} /> Blocked</span><span><XCircle size={14} /> Succeeded</span><span><CircleDot size={14} /> Partial</span></div></div><div className="results-table-scroll"><table className="results-table"><thead><tr><th>Case</th><th>Attack</th><th>Normal mode</th><th>Defended mode</th><th>Why this result</th></tr></thead><tbody>{normal.cases.map(item => { const defendedCase = defendedById.get(item.case_id); return <ResultRow key={item.case_id} normalCase={item} defendedCase={defendedCase} /> })}</tbody></table></div></div>
}

function ResultRow({ normalCase, defendedCase }: { normalCase: SuiteReport['cases'][number]; defendedCase?: SuiteReport['cases'][number] }) {
  const transcript = defendedCase?.transcript ?? normalCase.transcript
  const toolCalls = defendedCase?.tool_calls_made ?? normalCase.tool_calls_made
  return <tr><td><span className="case-code">{normalCase.case_id}</span><small>{normalCase.category}</small></td><td><strong>{normalCase.prompt}</strong></td><td><OutcomeBadge outcome={normalCase.outcome} /><span className="table-detail">{normalCase.rationale}</span></td><td>{defendedCase ? <><OutcomeBadge outcome={defendedCase.outcome} /><span className="table-detail">{defendedCase.rationale}</span></> : <span className="unknown-result">No defended result</span>}</td><td><span className="table-detail">{defendedCase?.answer || normalCase.answer || 'No answer recorded.'}</span><span className="table-meta">{defendedCase?.latency_ms ?? normalCase.latency_ms} ms · {toolCalls.length} tool calls</span><ToolCallDetails tools={toolCalls} /><details className="transcript-details"><summary>View transcript</summary><pre>{transcript.length ? JSON.stringify(transcript, null, 2) : 'No transcript recorded.'}</pre></details></td></tr>
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
  return <section><div className="page-heading compact"><div><div className="eyebrow"><AlertTriangle size={13} /> Test catalog</div><h1>Attack library</h1><p>Fixed synthetic cases used by the controlled security harness.</p></div><a className="button secondary link-button" href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API docs <ExternalLink size={14} /></a></div><div className="library-toolbar"><div className="search-field"><Search size={16} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Filter attack cases" /></div><span>{filtered.length} scenarios</span></div><div className="attack-grid">{filtered.map(item => <article className="attack-card" key={item.case_id}><div className="attack-card-top"><span className="case-code">{item.case_id}</span><span className="category-pill">{item.category}</span></div><h2>{item.category}</h2><p>{item.prompt}</p><div className="attack-card-footer"><span><LockKeyhole size={13} /> controlled input</span><ArrowUpRight size={16} /></div></article>)}</div>{filtered.length === 0 && <div className="empty-state">No attack cases match that filter.</div>}</section>
}

export default App
