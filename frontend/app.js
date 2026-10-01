const API = "";
const sessions = Array.from({length: 100}, (_, i) => `SESSION-${1001 + i}`);
const state = { busy: false, lastResult: null };
const byId = id => document.getElementById(id);
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[character]));

function fillSessionSelect(select) {
  select.innerHTML = sessions.map((session, index) => `<option value="${session}">${session} · Customer ${1001 + index}</option>`).join("");
  select.value = "SESSION-1001";
}

function sessionId() { return byId("session-select").value; }

function addMessage(role, text, tag = "") {
  const conversation = byId("conversation");
  const welcome = conversation.querySelector(".welcome-block");
  if (welcome) welcome.remove();
  const message = document.createElement("div");
  message.className = `chat-message ${role}`;
  const safeText = escapeHtml(text);
  message.innerHTML = `<div class="message-avatar">${role === "user" ? "C" : "V"}</div><div class="message-body"><div class="message-meta">${role === "user" ? "CUSTOMER" : "VERICOMMERCE ASSISTANT"} · ${new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}</div><div class="message-bubble">${safeText}${tag ? `<br><span class="bubble-tag">${escapeHtml(tag)}</span>` : ""}</div></div>`;
  conversation.appendChild(message);
  conversation.scrollTop = conversation.scrollHeight;
}

function showTyping() {
  const conversation = byId("conversation");
  const typing = document.createElement("div");
  typing.id = "typing-indicator";
  typing.className = "chat-message";
  typing.innerHTML = `<div class="message-avatar">V</div><div class="message-body"><div class="message-meta">VERITRUST · VERIFYING</div><div class="message-bubble"><span class="typing-dots"><i></i><i></i><i></i></span></div></div>`;
  conversation.appendChild(typing);
  conversation.scrollTop = conversation.scrollHeight;
}

function renderVerification(result) {
  byId("empty-verification").classList.add("hidden");
  byId("verification-details").classList.remove("hidden");
  const decision = (result.decision || "REVIEW").toUpperCase();
  const risk = (result.risk || "MEDIUM").toUpperCase();
  byId("decision-label").textContent = decision;
  byId("decision-label").style.color = decision === "APPROVE" ? "#168b78" : decision === "BLOCK" ? "#c9515c" : "#bd7a1e";
  byId("risk-chip").textContent = `${risk} RISK`;
  byId("risk-chip").className = `risk-chip ${risk.toLowerCase()}`;
  byId("verify-icon").textContent = decision === "APPROVE" ? "✓" : decision === "BLOCK" ? "⊘" : decision === "CORRECT" ? "↻" : "!";
  byId("verify-icon").className = `verify-icon ${decision.toLowerCase()}`;
  const securityStatus = String(result.security_status || "UNKNOWN").toUpperCase();
  byId("auth-status").textContent = ["DENIED", "UNAUTHENTICATED", "ORDER_UNVERIFIED", "ERROR"].includes(securityStatus) ? "BLOCKED" : "CHECKED";
  byId("evidence-status").textContent = result.sources?.length ? `${result.sources.length} SOURCES` : "NO SOURCES";
  byId("policy-status").textContent = decision === "BLOCK" ? "BLOCKED" : decision === "REVIEW" ? "REVIEW" : "CHECKED";
  byId("judge-status").textContent = decision === "CORRECT" ? "RECHECKED" : decision;
  byId("decision-reason").textContent = result.reason || (decision === "CORRECT" ? "The response was corrected and checked again against trusted evidence." : "Decision recorded with verification metadata.");
  renderSources(result.sources || []);
}

function renderSources(sources) {
  byId("source-count").textContent = sources.length;
  const target = byId("sources-list");
  if (!sources.length) {
    target.innerHTML = `<div class="source-empty">No external source was needed for this response.</div>`;
    return;
  }
  target.innerHTML = sources.map(source => {
    const type = source.source_type === "trusted_structured_database" ? "AUTHORIZED RECORD" : "COMPANY POLICY";
    const document = source.document_id || source.source || "Trusted source";
    const meta = [source.category, source.version ? `v${source.version}` : "", source.effective_date].filter(Boolean).join(" · ");
    return `<article class="source-item"><div class="source-item-top"><span class="source-title">${escapeHtml(document)}</span><span class="source-kind">${type}</span></div><div class="source-meta">${escapeHtml(meta)}${source.distance != null ? ` · distance ${Number(source.distance).toFixed(3)}` : ""}</div></article>`;
  }).join("");
}

async function sendMessage(message) {
  if (!message.trim() || state.busy) return;
  state.busy = true;
  const input = byId("message-input");
  input.value = "";
  byId("char-count").textContent = "0 / 4000";
  byId("send-button").disabled = true;
  addMessage("user", message);
  showTyping();
  try {
    const response = await fetch(`${API}/chat`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:sessionId(),message})});
    const result = await response.json();
    byId("typing-indicator")?.remove();
    if (!response.ok) throw new Error(result.detail || "The request could not be completed.");
    state.lastResult = result;
    addMessage("assistant", result.response || "No response was returned.", `${result.decision} · ${result.risk} RISK · ${result.latency_ms ?? 0} ms`);
    renderVerification(result);
    loadDashboard();
  } catch (error) {
    byId("typing-indicator")?.remove();
    addMessage("assistant", `I couldn’t reach the local service. ${error.message || "Check that the backend is running."}`);
  } finally {
    state.busy = false;
    byId("send-button").disabled = false;
    input.focus();
  }
}

function setView(view) {
  document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.view === view));
  document.querySelectorAll(".view").forEach(item => item.classList.remove("active"));
  byId(`${view}-view`).classList.add("active");
  byId("current-section").textContent = view === "chat" ? "CUSTOMER DESK" : "TRUST DASHBOARD";
  if (view === "dashboard") loadDashboard();
}

function attachSuggestions() {
  document.querySelectorAll(".suggestion").forEach(button => button.addEventListener("click", () => sendMessage(button.dataset.prompt)));
}

function resetConversationForSession() {
  byId("conversation").innerHTML = `<div class="welcome-block"><div class="welcome-symbol">✳</div><span class="eyebrow">VERIFIED SUPPORT</span><h3>Session changed</h3><p>Start a new conversation for the selected customer session.</p><div class="suggestion-grid"><button class="suggestion" data-prompt="Where is my order ORD-10001?"><span>↗</span><b>Track an order</b><small>Shipment status and estimate</small></button><button class="suggestion" data-prompt="What is the refund processing time?"><span>↺</span><b>Refund policy</b><small>Eligibility and processing</small></button><button class="suggestion" data-prompt="Does the SmartView 4K Monitor support HDMI?"><span>⌁</span><b>Product details</b><small>Ports and compatibility</small></button><button class="suggestion" data-prompt="I forgot my password. What should I do?"><span>◇</span><b>Account security</b><small>Safe recovery guidance</small></button></div></div>`;
  byId("empty-verification").classList.remove("hidden");
  byId("verification-details").classList.add("hidden");
  byId("verify-icon").textContent = "—";
  byId("verify-icon").className = "verify-icon neutral";
  byId("source-count").textContent = "0";
  byId("sources-list").innerHTML = `<div class="source-empty">Sources will appear with the verified response.</div>`;
  attachSuggestions();
}

function decisionBadge(decision) {
  const value = String(decision || "REVIEW").toUpperCase();
  const className = value === "APPROVE" ? "approve" : value === "CORRECT" ? "correct" : value === "BLOCK" ? "block" : "review";
  return `<span class="decision-badge ${className}">${escapeHtml(value)}</span>`;
}

function renderAudit(events) {
  const rows = byId("audit-rows");
  if (!events?.length) {
    rows.innerHTML = `<tr><td colspan="6" class="table-empty">No audit events for this session yet.</td></tr>`;
    return;
  }
  rows.innerHTML = events.map(event => `<tr><td>${escapeHtml(String(event.request_id || "").slice(0, 12))}…</td><td class="query-cell" title="${escapeHtml(event.user_query)}">${escapeHtml(event.user_query)}</td><td>${escapeHtml(event.query_category || "general")}</td><td>${decisionBadge(event.decision)}</td><td><span class="risk-badge ${(event.risk || "medium").toLowerCase()}">${escapeHtml(event.risk || "MEDIUM")}</span></td><td>${Math.round(event.latency_ms || 0)} ms</td></tr>`).join("");
}

function setText(id, value) { byId(id).textContent = value ?? 0; }

async function loadDashboard() {
  try {
    const [metricsResponse, auditResponse] = await Promise.all([
      fetch(`${API}/metrics`),
      fetch(`${API}/audit/recent?session_id=${encodeURIComponent(byId("audit-session-select").value)}&limit=12`)
    ]);
    const metrics = await metricsResponse.json();
    const audit = await auditResponse.json();
    setText("metric-total", metrics.total_requests);
    setText("metric-approved", metrics.approved);
    setText("metric-corrected", metrics.corrected);
    setText("metric-blocked", metrics.blocked);
    setText("metric-reviewed", metrics.reviewed);
    const total = metrics.total_requests || 0;
    const low = metrics.low_risk || 0;
    const high = metrics.high_risk || 0;
    const other = Math.max(0, total - low - high);
    setText("risk-total", total); setText("risk-low", low); setText("risk-high", high); setText("risk-other", other);
    const lowAngle = total ? (low / total) * 360 : 0;
    const highAngle = total ? (high / total) * 360 : 0;
    byId("risk-ring").style.background = `conic-gradient(#16b394 0deg ${lowAngle}deg,#d85b67 ${lowAngle}deg ${lowAngle + highAngle}deg,#e9edf2 ${lowAngle + highAngle}deg 360deg)`;
    setText("latency-value", `${Math.round(metrics.average_latency_ms || 0)} ms`);
    setText("latency-retrieval", `${Math.round(metrics.retrieval_latency_ms || 0)} ms`);
    setText("latency-maker", `${Math.round(metrics.maker_latency_ms || 0)} ms`);
    setText("latency-judge", `${Math.round(metrics.judge_latency_ms || 0)} ms`);
    setText("latency-correction", `${Math.round(metrics.correction_latency_ms || 0)} ms`);
    const normalizedLatency = Math.min(100, ((metrics.average_latency_ms || 0) / 5000) * 100);
    byId("latency-bar").style.width = `${normalizedLatency}%`;
    const dataset = metrics.dataset || {};
    setText("data-customers", dataset.customers); setText("data-orders", dataset.orders); setText("data-payments", dataset.payments);
    setText("data-refunds", dataset.refunds); setText("data-returns", dataset.returns); setText("data-shipments", dataset.shipments);
    setText("data-products", dataset.products); setText("data-promotions", dataset.promotions); setText("data-cases", dataset.support_cases);
    renderAudit(audit.events || []);
  } catch (_) {
    // The chat remains usable if dashboard telemetry is unavailable.
  }
}

async function loadHealth() {
  try {
    const response = await fetch(`${API}/health`);
    const data = await response.json();
    byId("kb-status").textContent = `${data.knowledge_base_documents} docs · ${data.knowledge_base_chunks} chunks`;
  } catch (_) { byId("kb-status").textContent = "Backend not connected"; }
}

document.addEventListener("DOMContentLoaded", () => {
  fillSessionSelect(byId("session-select"));
  fillSessionSelect(byId("audit-session-select"));
  document.querySelectorAll(".nav-item").forEach(item => item.addEventListener("click", () => setView(item.dataset.view)));
  attachSuggestions();
  byId("chat-form").addEventListener("submit", event => { event.preventDefault(); sendMessage(byId("message-input").value); });
  byId("message-input").addEventListener("input", event => { byId("char-count").textContent = `${event.target.value.length} / 4000`; event.target.style.height = "auto"; event.target.style.height = `${Math.min(event.target.scrollHeight, 100)}px`; });
  byId("audit-session-select").addEventListener("change", loadDashboard);
  byId("session-select").addEventListener("change", () => { resetConversationForSession(); byId("audit-session-select").value = sessionId(); loadDashboard(); });
  byId("refresh-dashboard").addEventListener("click", loadDashboard);
  loadHealth();
  loadDashboard();
});
