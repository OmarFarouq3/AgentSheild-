"use strict";
const $ = id => document.getElementById(id);
const categories = {direct_injection:"Direct injection",indirect_injection:"Indirect injection",tool_misuse:"Tool misuse",exfiltration:"Exfiltration"};
let data = null;
let liveBusy = false;
const liveResults = new Map();
const pct = value => value == null ? "Not evaluated" : `${value.toFixed(2).replace(/\.00$/, "")}%`;
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const badge = status => `<span class="badge ${esc(status)}">${esc(status.replaceAll("_", " "))}</span>`;
const json = value => JSON.stringify(value, null, 2);
function notify(text) { $("notice").textContent = text; $("notice").hidden = !text; }
async function request(url, options) {
  const response = await fetch(url, options);
  let body;
  try { body = await response.json(); } catch { throw new Error("The dashboard API returned an unreadable response."); }
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "The request could not be completed.");
  return body;
}
function caseFor(mode, id) { return data[mode].cases.find(item => item.attack_id === id); }
function metric(label, value, note, kind="") {
  return `<article class="metric ${kind}"><span class="label">${label}</span><strong>${value}</strong><small>${note}</small></article>`;
}
function chart(label, before, after) {
  const line = (value, kind) => `<div class="bar-line"><div class="bar-track"><div class="bar-fill ${kind}" style="width:${Number(value) || 0}%"></div></div><span class="bar-value">${value == null ? "N/A" : pct(value)}</span></div>`;
  return `<div class="chart-row" aria-label="${esc(label)}: baseline ${pct(before)}, defended ${pct(after)}"><span class="chart-label">${label}</span><div class="bars">${line(before, "")}${line(after, "after")}</div></div>`;
}
function render() {
  const c = data.comparison, b = c.baseline, d = c.defended, m = c.matched;
  $("model-label").textContent = data.defended.model || "Local Qwen 3.5 4B";
  $("metrics").innerHTML = metric("Frozen baseline ASR",pct(b.asr_percent),`${b.COMPROMISED} compromised / ${b.valid_evaluated_attacks} valid`,"baseline")
    + metric("Defended ASR",pct(d.asr_percent),`${d.COMPROMISED} compromised / ${d.valid_evaluated_attacks} valid`,"defended")
    + metric("Matched ASR reduction",m.absolute_reduction_pp == null ? "N/A" : `${m.absolute_reduction_pp} <span style="font-size:18px">pp</span>`,`${m.count} attacks evaluated in both postures`,"reduction")
    + metric("Catalog coverage",`${m.count} <span style="color:#6c7e92;font-size:24px">/ ${b.total_catalog_attacks}</span>`,`${c.excluded_or_unmatched.length} excluded or unmatched`);
  $("charts").innerHTML = chart("Overall",m.baseline.asr_percent,m.defended.asr_percent) + Object.entries(categories).map(([key,label]) => chart(label,m.baseline.per_category[key]?.asr_percent,m.defended.per_category[key]?.asr_percent)).join("");
  $("outcome").innerHTML = `<div class="outcome-number">${c.fixed_attacks.length}<span style="font-size:25px;color:#8195a8"> / ${b.COMPROMISED}</span></div><div class="outcome-label">baseline compromises blocked</div><p class="outcome-sub">${c.still_compromised.length} observed compromises remain in the defended run.</p>`;
  renderTable();
  $("finding-cards").innerHTML = c.attacks.filter(row => row.baseline_result === "COMPROMISED").map(row => {
    const before = caseFor("baseline", row.attack_id);
    const disclosed = before.evaluation.observed_criteria.includes("sensitive_data_leaked");
    return `<article class="finding"><div class="finding-header"><strong>${row.attack_id}</strong>${badge(row.defended_result)}</div><h3>${esc(row.name)}</h3><p>The baseline ${disclosed ? "disclosed the synthetic confidential canary" : "executed the sensitive document tool"}. Its exposed playbook tool required no verified user authorization.</p><p><b>Defended evidence:</b> ${esc(row.defense_attribution)}. ${row.fixed ? "No configured compromise criterion was observed." : "Review the remaining exposure."}</p><button class="evidence-button" data-detail="${row.attack_id}">Inspect before / after ↗</button></article>`;
  }).join("");
  $("coverage-counts").innerHTML = `<div class="coverage-row"><span>Baseline valid evaluations</span><strong>${b.valid_evaluated_attacks} / ${b.total_catalog_attacks}</strong></div><div class="coverage-row"><span>Defended valid evaluations</span><strong>${d.valid_evaluated_attacks} / ${d.total_catalog_attacks}</strong></div><div class="coverage-row"><span>Not exercised · baseline / defended</span><strong>${b.NOT_EXERCISED} / ${d.NOT_EXERCISED}</strong></div><div class="coverage-row"><span>Errors · baseline / defended</span><strong>${b.ERROR} / ${d.ERROR}</strong></div>`;
  $("exclusions").innerHTML = `<details><summary>${c.excluded_or_unmatched.length} excluded or unmatched cases</summary>${c.attacks.filter(row => !row.matched_evaluation).map(row => `<div class="excluded-item"><b>${row.attack_id}</b>${esc(caseFor("baseline",row.attack_id).evaluation.reasons.join("; "))}</div>`).join("")}</details>`;
  $("risk-list").innerHTML = c.remaining_risks.map(risk => `<li>${esc(risk)}</li>`).join("");
  $("audit-note").textContent = `${c.audit_note} Baseline SHA-256: ${c.provenance["baseline_results.json"]}`;
  const prior = $("demo-attack").value;
  $("demo-attack").innerHTML = data.baseline.cases.filter(item => ["READY","ADAPTED"].includes(item.classification)).map(item => `<option value="${item.attack_id}">${item.attack_id} · ${esc(item.name)}</option>`).join("");
  $("demo-attack").value = prior || "TM-001";
}
function renderTable() {
  if (!data) return;
  const cat = $("category-filter").value, status = $("result-filter").value, severity = $("severity-filter").value;
  const rows = data.comparison.attacks.filter(row => (!cat || row.category === cat) && (!status || [row.baseline_result,row.defended_result].includes(status)) && (!severity || row.severity === severity));
  $("table-count").textContent = `${rows.length} of ${data.comparison.attacks.length} attacks`;
  $("empty-table").hidden = rows.length > 0;
  $("attack-rows").innerHTML = rows.map(row => `<tr><td><strong>${row.attack_id}</strong><small>${categories[row.category] || esc(row.category)}</small></td><td><span class="severity">${esc(row.severity)}</span></td><td>${badge(row.baseline_result)}</td><td>${badge(row.defended_result)}</td><td class="${row.fixed ? "change-fixed" : "muted"}">${row.fixed ? "↗ " : ""}${esc(row.change)}</td><td><button class="evidence-button" data-detail="${row.attack_id}" aria-label="View evidence for ${row.attack_id}">View evidence ↗</button></td></tr>`).join("");
}
function evidencePane(item, mode) {
  if (!item) return `<article class="evidence-pane"><h3>${mode}</h3><p>No evidence available.</p></article>`;
  return `<article class="evidence-pane ${mode}"><h3>${mode.toUpperCase()} ${badge(item.evaluation.result)}</h3><p>${item.latency_ms == null ? "No runtime latency" : `${(item.latency_ms / 1000).toFixed(2)}s runtime`} · ${item.tools_called.length} executed tool calls</p><h4>Final response</h4><pre>${esc(item.response || "No response — case not executed.")}</pre><h4>Evaluation reasons</h4><pre>${esc(json(item.evaluation.reasons))}</pre><details><summary>Tool calls & arguments</summary><pre>${esc(json(item.tools_called))}</pre></details><details><summary>Intercepted requests (not transmitted)</summary><pre>${esc(json(item.intercepted_tool_calls))}</pre></details><details><summary>Criteria & coverage</summary><pre>${esc(json(item.evaluation))}</pre></details><details><summary>Full transcript</summary><pre>${esc(json(item.transcript))}</pre></details></article>`;
}
function showDetail(id) {
  if (!data) return;
  const before = caseFor("baseline",id), after = caseFor("defended",id), row = data.comparison.attacks.find(r => r.attack_id === id);
  $("detail-content").innerHTML = `<h2>${id} · ${esc(before.name)}</h2><p>${esc(row.change)} · ${esc(row.defense_attribution)}</p><h4>Prompt</h4><pre>${esc(before.prompt)}</pre><p><b>Objective:</b> ${esc(before.attack.objective || before.attack.original_definition?.objective)}</p><p><b>Expected safe behavior:</b> ${esc(before.expected_safe_behavior)}</p><p><b>Execution classification:</b> ${esc(before.classification)} — ${esc(before.classification_reason)}</p><div class="evidence-columns">${evidencePane(before,"baseline")}${evidencePane(after,"defended")}</div><details><summary>Evidence integrity hashes</summary><pre>${esc(json({baseline:row.baseline_evidence_hash,defended:row.defended_evidence_hash}))}</pre></details>`;
  $("detail").showModal();
}
async function load() {
  notify("Loading and verifying saved evidence…"); $("refresh").disabled = true;
  try { data = await request("/dashboard-api/data"); render(); notify(""); }
  catch(error) { notify(`${error.message} Recorded files are required; use Reload evidence after generating them.`); }
  finally { $("refresh").disabled = false; }
}
function renderLive() {
  const id = $("demo-attack").value;
  $("live-output").innerHTML = ["baseline","defended"].map(mode => liveResults.has(`${id}:${mode}`) ? evidencePane(liveResults.get(`${id}:${mode}`),mode) : `<article class="evidence-pane ${mode}"><h3>${mode.toUpperCase()} · LIVE</h3><p>Run this posture to compare fresh evidence. Recorded evidence remains unchanged.</p></article>`).join("");
}
async function runLive(mode) {
  if (liveBusy || !data) return;
  liveBusy = true;
  const id = $("demo-attack").value;
  $("run-baseline").disabled = $("run-defended").disabled = $("demo-attack").disabled = true;
  $("live-status").textContent = `${id} · ${mode}: running against local Ollama. This may take up to three minutes. Recorded comparison is still available.`;
  try {
    const started = await request("/dashboard-api/live",{method:"POST",headers:{"Content-Type":"application/json"},body:json({attack_id:id,security_mode:mode})});
    const deadline = Date.now() + 195000;
    let job;
    while(Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve,1200));
      job = await request(`/dashboard-api/live/${started.job_id}`);
      if(job.status !== "running") break;
    }
    if(!job || job.status === "running") throw new Error("Live run is taking longer than expected. Use recorded evidence; server may still be finishing.");
    if(job.status === "error") throw new Error(job.error);
    const item = job.report.cases[0];
    liveResults.set(`${id}:${mode}`,item); renderLive();
    $("live-status").textContent = `${id} · ${mode}: ${item.evaluation.result}. Fresh evidence saved separately; historical metrics above have not changed.`;
  } catch(error) { $("live-status").textContent = `${error.message} Use View recorded comparison for the demo fallback.`; }
  finally { liveBusy = false; $("run-baseline").disabled = $("run-defended").disabled = $("demo-attack").disabled = false; }
}
Object.entries(categories).forEach(([value,label]) => $("category-filter").add(new Option(label,value)));
["category-filter","result-filter","severity-filter"].forEach(id => $(id).addEventListener("change",renderTable));
$("clear-filters").onclick = () => { ["category-filter","result-filter","severity-filter"].forEach(id => $(id).value=""); renderTable(); };
$("refresh").onclick = load;
$("close-detail").onclick = () => $("detail").close();
document.addEventListener("click",event => { const button = event.target.closest("[data-detail]"); if(button) showDetail(button.dataset.detail); });
$("recorded-button").onclick = () => { if(data) showDetail($("demo-attack").value); };
$("run-baseline").onclick = () => runLive("baseline");
$("run-defended").onclick = () => runLive("defended");
$("demo-attack").onchange = renderLive;
document.querySelectorAll("nav a").forEach(link => link.addEventListener("click",() => { document.querySelectorAll("nav a").forEach(a => a.classList.remove("active")); link.classList.add("active"); }));
let chatBusy = false;
$("chat-clear").onclick = () => {
  $("chat-history").replaceChildren();
  $("chat-message").value = "";
  $("chat-status").textContent = "";
};
$("chat-form").onsubmit = async event => {
  event.preventDefault();
  const message = $("chat-message").value.trim(), mode = $("chat-mode").value;
  if (!message || chatBusy) return;
  chatBusy = true;
  ["chat-send", "chat-clear", "chat-mode", "chat-message"].forEach(id => $(id).disabled = true);
  const turn = document.createElement("article");
  turn.className = `evidence-pane ${mode}`;
  turn.innerHTML = `<h3>${esc(mode.toUpperCase())} / Interactive demo</h3><h4>User message</h4><pre>${esc(message)}</pre>`;
  $("chat-history").append(turn);
  $("chat-status").textContent = "Agent running locally (up to three minutes)...";
  try {
    const result = await request("/dashboard-api/chat", {method:"POST", headers:{"Content-Type":"application/json"}, body:json({message, security_mode:mode})});
    turn.insertAdjacentHTML("beforeend", `<h4>Agent final response</h4><pre>${esc(result.response)}</pre><p>Runtime: ${esc(result.latency_ms)} ms</p><details><summary>Executed tool calls and arguments (${result.tools_called.length})</summary><pre>${esc(json(result.tools_called))}</pre></details>`
      + (result.intercepted_tool_calls.length ? `<details><summary>Intercepted requests (not transmitted)</summary><pre>${esc(json(result.intercepted_tool_calls))}</pre></details>` : "")
      + (result.security_events.length ? `<details><summary>Guard / security events</summary><pre>${esc(json(result.security_events))}</pre></details>` : ""));
    $("chat-message").value = "";
    $("chat-status").textContent = "Response received. Historical metrics are unchanged.";
  } catch (error) {
    const failure = document.createElement("p");
    failure.textContent = error.message;
    turn.append(failure);
    $("chat-status").textContent = "Chat request failed. You can retry.";
  } finally {
    chatBusy = false;
    ["chat-send", "chat-clear", "chat-mode", "chat-message"].forEach(id => $(id).disabled = false);
  }
};
load();
