"use strict";

/* Operator console for Munich Rental Copilot.
   Every dynamic string goes through esc(): applicant messages are untrusted input. */

const USER_KEY = "rental-copilot-user";
const state = { users: [], user: null, inquiries: [], selected: null, detail: null, filter: "all", view: "inbox" };

const STATE_LABEL = {
  inquiry_received: "New",
  inquiry_classified: "Drafting",
  reply_draft_ready: "Drafting",
  reply_human_review: "Draft ready for review",
  reply_approved: "Approved, not sent yet",
  conversation_active: "Replied",
  needs_human_review: "Needs you",
  viewing_proposed: "Slots offered",
  viewing_confirmed: "Viewing booked",
  do_not_contact: "Do not contact",
  data_deletion_requested: "Data erased",
  tool_failure: "Tool failed",
  closed: "Closed",
};
const STATE_TONE = {
  inquiry_received: "new", inquiry_classified: "progress", reply_draft_ready: "progress",
  reply_human_review: "review", reply_approved: "progress", conversation_active: "progress",
  needs_human_review: "attention", tool_failure: "attention", viewing_proposed: "progress",
  viewing_confirmed: "done", do_not_contact: "stopped", data_deletion_requested: "stopped", closed: "stopped",
};
const FILTERS = [
  ["all", "All", () => true],
  ["attention", "Needs you", (s) => s === "needs_human_review" || s === "tool_failure"],
  ["review", "To review", (s) => s === "reply_human_review"],
  ["new", "New", (s) => s === "inquiry_received"],
  ["progress", "In progress", (s) => ["reply_approved", "conversation_active", "viewing_proposed", "viewing_confirmed"].includes(s)],
  ["stopped", "Stopped or closed", (s) => ["do_not_contact", "data_deletion_requested", "closed"].includes(s)],
];
const EMPTY_TEXT = {
  all: "No inquiries yet. Add a test inquiry to try the copilot.",
  attention: "Nothing needs you right now.",
  review: "No drafts are waiting for review.",
  new: "No new inquiries.",
  progress: "Nothing in progress yet.",
  stopped: "No stopped or closed inquiries.",
};
const INTENT_LABEL = {
  viewing_request: "Viewing request", availability_question: "Availability", cost_question: "Costs",
  property_detail_question: "Flat details", process_question: "Process", info_submission: "Sent documents",
  generic_or_incomplete: "Generic", stop_or_deletion_request: "Stop or deletion", complaint_or_hostile: "Complaint",
  negotiation_or_special_request: "Negotiation", legal_or_sensitive: "Legal or sensitive", spam_or_scam: "Spam",
};
const NEXT_ACTION_LABEL = {
  review_and_approve_draft: "Review and approve the draft",
  review_blocked_draft: "Rewrite the blocked draft",
  handle_manually: "Handle this one yourself",
  stop_all_contact: "No further contact",
  confirm_deletion_manually: "Confirm the deletion to the applicant",
  confirm_spam_and_close: "Confirm it is spam and close it",
};
const FACT_STATUS_LABEL = {
  verified: "Verified", extracted: "Extracted, not confirmed", user_entered: "Entered, no document",
  inferred: "Inferred by a model", unknown: "Unknown",
};
const SENSITIVE_LABEL = {
  family_status: "family status", origin_or_nationality: "origin or nationality", religion: "religion",
  health_or_disability: "health or disability", gender_or_age: "gender or age", financial_identifier: "a bank identifier",
};
const EVENT_LABEL = {
  agent_started: "Copilot started", state_changed: "State", tool_called: "Tool used", tool_failed: "Tool failed",
  tool_rejected: "Tool rejected the input", tool_denied: "Tool call denied", model_call: "Model call",
  classified: "Classified", draft_created: "Draft created", agent_output: "Copilot finished",
  draft_approved: "Draft approved", draft_rejected: "Draft rejected", reply_marked_sent: "Marked as sent",
  viewing_confirmed: "Viewing booked", inquiry_ingested: "Inquiry added",
};
const ALERT_FLAGS = ["prompt_injection_suspected", "sensitive_data_in_message", "draft_blocked", "tool_failure",
  "model_error", "contact_blocked", "ambiguous_opt_out", "deletion_request", "opt_out", "unsolicited_documents"];

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function safeGet(key) { try { return localStorage.getItem(key); } catch { return null; } }
function safeSet(key, value) { try { localStorage.setItem(key, value); } catch { /* storage unavailable */ } }

const timeFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const clockFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const fmtTime = (iso) => (iso ? timeFmt.format(new Date(iso)) : "");
const fmtClock = (iso) => (iso ? clockFmt.format(new Date(iso)) : "");
const toneClass = (s) => `tone-${STATE_TONE[s] || "stopped"}`;
const isAlert = (flag) => ALERT_FLAGS.includes(flag.split(":")[0]);
const isOperator = () => state.user && state.user.role === "operator";

function flagLabel(flag) {
  const [key, detail] = flag.split(":");
  switch (key) {
    case "prompt_injection_suspected": return "Possible prompt injection";
    case "sensitive_data_in_message": return `Mentions ${SENSITIVE_LABEL[detail] || detail}`;
    case "human_only_intent": return "Human-only topic";
    case "unsolicited_documents": return "Unrequested documents";
    case "low_confidence": return "Low confidence";
    case "contact_blocked": return "Earlier stop or deletion";
    case "ambiguous_opt_out": return "Conditional stop request";
    case "opt_out": return "Stop request";
    case "deletion_request": return "Deletion request";
    case "draft_blocked": return "Draft blocked by checks";
    case "no_viewing_slots": return "No free viewing slots";
    case "tool_failure": return `Tool failed: ${detail}`;
    case "model_error": return `Model error: ${detail}`;
    case "unsupported_language": return "Language not supported";
    default: return flag;
  }
}

function actorLabel(actor) {
  if (actor === "system:agent") return "Copilot";
  const [kind, id] = actor.split(":");
  if (kind === "operator") return (state.users.find((u) => u.user_id === id) || {}).display_name?.split(" (")[0] || id;
  if (kind === "applicant") return "Applicant (simulated)";
  return actor;
}

function eventDetail(e) {
  const p = e.payload || {};
  switch (e.event_type) {
    case "state_changed": return `${STATE_LABEL[p.from_state] || p.from_state} → ${STATE_LABEL[p.to_state] || p.to_state}`;
    case "tool_called": case "tool_failed": case "tool_rejected": case "tool_denied":
      return [p.tool, p.attempt ? `attempt ${p.attempt}` : "", p.error || ""].filter(Boolean).join(", ");
    case "model_call":
      return [p.tool, p.ok === false ? `failed (${p.error})` : `${p.latency_ms} ms`,
        p.input_tokens != null ? `${p.input_tokens} tokens in, ${p.output_tokens} out` : ""].filter(Boolean).join(", ");
    case "classified": return `${INTENT_LABEL[p.intent] || p.intent}, ${Math.round((p.confidence || 0) * 100)}% confidence`;
    case "draft_created": return `${p.draft_status}${p.finding_codes?.length ? `, checks: ${p.finding_codes.join(", ")}` : ""}`;
    case "draft_approved": return [p.edited ? "edited" : "unchanged", p.override ? "with override" : ""].filter(Boolean).join(", ");
    case "agent_output": return NEXT_ACTION_LABEL[p.next_best_action] || p.next_best_action || "";
    case "viewing_confirmed": return p.slot_id || "";
    default: return "";
  }
}

/* ------------------------------------------------------------------ network */
async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", "X-User-Id": state.user ? state.user.user_id : "" },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const error = new Error((data && data.detail) || `Request failed (${res.status})`);
    error.status = res.status;
    error.data = data;
    throw error;
  }
  return data;
}

let toastTimer;
function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("is-error", isError);
  el.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("is-visible"), 3600);
}

/* ------------------------------------------------------------------ list */
function renderFilters() {
  $("#filters").innerHTML = FILTERS.map(([key, label, fn]) => {
    const count = state.inquiries.filter((i) => fn(i.state)).length;
    return `<button class="filter" role="tab" aria-selected="${state.filter === key}" data-filter="${key}">` +
      `${esc(label)}<span class="count">${count}</span></button>`;
  }).join("");
}

function renderList() {
  const fn = FILTERS.find((f) => f[0] === state.filter)[2];
  const items = state.inquiries.filter((i) => fn(i.state));
  if (!items.length) {
    $("#inquiry-list").innerHTML = `<li class="empty">${esc(EMPTY_TEXT[state.filter])}</li>`;
    return;
  }
  $("#inquiry-list").innerHTML = items.map((i) => {
    const alerts = (i.risk_flags || []).filter(isAlert).slice(0, 2)
      .map((f) => `<span class="chip chip-alert">${esc(flagLabel(f))}</span>`).join("");
    const intent = i.intent ? `<span class="chip">${esc(INTENT_LABEL[i.intent] || i.intent)}</span>` : "";
    return `<li><button class="inquiry-row" data-id="${esc(i.inquiry_id)}" aria-current="${i.inquiry_id === state.selected}">
      <span class="row-name">${esc(i.applicant_display_name || "Unnamed applicant")}</span>
      <span class="row-time">${esc(fmtTime(i.received_at))}</span>
      <span class="row-preview">${esc(i.erased ? "Content erased on request." : i.preview)}</span>
      <span class="row-meta"><span class="state ${toneClass(i.state)}">${esc(STATE_LABEL[i.state] || i.state)}</span>${intent}${alerts}</span>
    </button></li>`;
  }).join("");
}

/* ------------------------------------------------------------------ detail */
function readingBlock(run) {
  const flags = run.risk_flags || [];
  const lang = { de: "German", en: "English", other: "Other" }[run.language] || run.language;
  return `<section class="block"><h3>Copilot's reading</h3>
    <dl class="reading">
      <div><dt>Intent</dt><dd>${esc(run.intent ? INTENT_LABEL[run.intent] || run.intent : "Not classified")}</dd></div>
      <div><dt>Confidence</dt><dd>${run.intent ? `${Math.round(run.confidence * 100)}%` : "Not classified"}</dd></div>
      <div><dt>Language</dt><dd>${esc(lang)}</dd></div>
      <div><dt>Next step</dt><dd>${esc(NEXT_ACTION_LABEL[run.next_best_action] || run.next_best_action)}</dd></div>
    </dl>
    ${flags.length ? `<div class="flags">${flags.map((f) => `<span class="chip ${isAlert(f) ? "chip-alert" : ""}">${esc(flagLabel(f))}</span>`).join("")}</div>` : ""}
    <p class="rationale">${esc(run.decision_rationale)} Model: ${esc(run.provider)}, prompt ${esc(run.prompt_version)}.</p>
  </section>`;
}

function marginBlock(d) {
  const run = d.run;
  const draft = d.draft;
  const labels = Object.fromEntries(d.unit.facts.map((f) => [f.field, f.label_en]));
  const parts = [];
  if (draft && draft.author === "operator") {
    parts.push(`<div><h4>Evidence</h4><p class="hint">Written by an operator. Numbers are checked against the verified fact sheet.</p></div>`);
  } else if (run && run.property_facts_used && run.property_facts_used.length) {
    parts.push(`<div><h4>Facts used</h4><ul>${run.property_facts_used.map((f) => `<li class="evidence-item">
        <span>${esc(labels[f.field] || f.field)}</span><span class="value">${esc(f.value)}</span>
        <span class="source"><span class="status st-${esc(f.status)}">${esc(FACT_STATUS_LABEL[f.status] || f.status)}</span>, ${esc(f.source_reference)}</span>
      </li>`).join("")}</ul></div>`);
  } else {
    parts.push(`<div><h4>Facts used</h4><p class="hint">None.</p></div>`);
  }
  if (run && run.unknowns && run.unknowns.length) {
    parts.push(`<div><h4>Left open</h4><ul>${run.unknowns.map((u) => `<li><span class="status st-unknown">${esc(labels[u] || u)}</span></li>`).join("")}</ul>
      <p class="hint">Not confirmed on the fact sheet, so the reply leaves it open.</p></div>`);
  }
  const offered = draft && draft.proposed_slot_ids ? d.slots.filter((s) => draft.proposed_slot_ids.includes(s.slot_id)) : [];
  if (offered.length) {
    parts.push(`<div><h4>Slots offered</h4><ul>${offered.map((s) => `<li>${esc(s.display)}${s.free ? "" : " (booked)"}</li>`).join("")}</ul></div>`);
  }
  const findings = (draft && draft.findings) || [];
  parts.push(`<div><h4>Checks</h4>${findings.length
    ? `<ul>${findings.map((f) => `<li class="finding ${f.severity === "block" ? "block-level" : ""}"><strong>${f.severity === "block" ? "Blocks approval" : "Warning"}</strong>${esc(f.message)}</li>`).join("")}</ul>`
    : `<p class="hint">All checks passed: only verified facts, every number backed by evidence, no early document requests.</p>`}</div>`);
  return `<aside class="margin" aria-label="Evidence and checks">${parts.join("")}</aside>`;
}

function letter(content) {
  return `<div class="letter-wrap"><div class="letter">${content}</div>${marginBlock(state.detail)}</div>`;
}

function replyBlock(d, dis) {
  const inq = d.inquiry;
  const draft = d.draft;
  const s = inq.state;
  if (s === "reply_human_review" && draft && draft.status === "pending_review") {
    return `<section class="block"><h3>Draft reply</h3>
      <p class="hint">Edit freely. Approving re-runs the checks on your final text. Nothing is sent from here.</p>
      ${letter(`<label class="visually-hidden" for="draft-text">Draft reply</label><textarea id="draft-text" rows="12" ${dis}>${esc(draft.text)}</textarea>`)}
      <div id="override-slot"></div>
      <div class="actions"><button class="btn btn-primary" data-action="approve" ${dis}>Approve reply</button>
        <button class="btn" data-action="reject" ${dis}>Reject draft</button></div></section>`;
  }
  if (s === "needs_human_review") {
    const blocked = draft && draft.status === "blocked";
    const intro = blocked
      ? "The checks blocked the copilot's draft. Rewrite it below; your text is checked again before approval."
      : "The copilot did not draft a reply here. Write it yourself, or close the inquiry without a reply.";
    return `<section class="block"><h3>Your reply</h3><p class="hint">${esc(intro)}</p>
      ${letter(`<label class="visually-hidden" for="draft-text">Your reply</label><textarea id="draft-text" rows="10" placeholder="Guten Tag, …" ${dis}>${esc(blocked ? draft.text : "")}</textarea>`)}
      <div class="actions"><button class="btn btn-primary" data-action="manual" ${dis}>Submit for approval</button></div></section>`;
  }
  if (draft && (draft.status === "approved" || draft.status === "sent")) {
    const text = draft.final_text || draft.text || "";
    const approvedNote = draft.status === "approved"
      ? "Approved. Copy the text, send it from your mailbox or the portal, then mark it as sent."
      : `Sent by an operator${draft.reviewed_by ? ` (approved by ${esc(draft.reviewed_by)})` : ""}.`;
    let actions = "";
    if (s === "reply_approved") {
      actions = `<div class="actions"><button class="btn" data-action="copy">Copy text</button>
        <button class="btn btn-primary" data-action="sent" ${dis}>Mark as sent</button></div>`;
    }
    let slots = "";
    if (s === "viewing_proposed") {
      const offered = d.slots.filter((x) => draft.proposed_slot_ids.includes(x.slot_id));
      slots = `<div class="block"><h3>Applicant's answer (simulated)</h3><p class="hint">In the demo you play the applicant: pick the slot they accepted.</p>
        <div class="slots">${offered.map((x) => `<button class="btn" data-action="accept" data-slot="${esc(x.slot_id)}" ${x.free ? "" : "disabled"} ${dis}>${esc(x.display)}</button>`).join("")}</div></div>`;
    }
    return `<section class="block"><h3>Reply</h3><p class="hint">${approvedNote}</p>
      ${letter(`<div class="letter-text">${esc(text)}</div>`)}${actions}${slots}</section>`;
  }
  if (s === "do_not_contact" || s === "data_deletion_requested") {
    return `<section class="block"><h3>Reply</h3><p class="hint">No reply. Contact with this applicant is stopped.</p></section>`;
  }
  return "";
}

function controlBlock(d, dis) {
  const next = d.allowed_next_states || [];
  const buttons = [];
  if (d.inquiry.state === "inquiry_received") buttons.push(`<button class="btn btn-primary" data-action="process" ${dis}>Run copilot</button>`);
  if (next.includes("closed")) buttons.push(`<button class="btn" data-action="close" ${dis}>Close inquiry</button>`);
  buttons.push(`<span class="spacer"></span>`);
  if (next.includes("do_not_contact")) buttons.push(`<button class="btn btn-danger" data-action="stop" ${dis}>Stop contact</button>`);
  if (next.includes("data_deletion_requested")) buttons.push(`<button class="btn btn-danger" data-action="erase" ${dis}>Erase applicant data</button>`);
  return `<section class="block"><div class="actions">${buttons.join("")}</div></section>`;
}

function renderDetail() {
  const pane = $("#detail");
  const d = state.detail;
  if (!d) {
    pane.innerHTML = `<p class="empty">Select an inquiry to see the copilot's reading, its draft and the evidence behind it.</p>`;
    return;
  }
  const inq = d.inquiry;
  const dis = isOperator() ? "" : `disabled title="Viewers can read but not change inquiries"`;
  const message = inq.erased_at ? "This content was erased on the applicant's request." : inq.message;
  const openTasks = d.tasks.filter((t) => t.status === "open");
  pane.innerHTML = `
    <button class="btn btn-quiet back" data-action="back">Back to inbox</button>
    <header class="detail-head">
      <h2>${esc(inq.applicant_display_name || "Unnamed applicant")}</h2>
      <span class="state ${toneClass(inq.state)}">${esc(STATE_LABEL[inq.state] || inq.state)}</span>
      <p class="sub">${esc(d.unit.title)}, ${esc(d.unit.district)}. Received ${esc(fmtTime(inq.received_at))}. Contact channel: ${esc(inq.contact_channel || "none given")}.</p>
    </header>
    <section class="block"><h3>Applicant's message</h3>
      <p class="hint">Untrusted input. The copilot reads it as data, never as instructions.</p>
      <blockquote class="message">${esc(message)}</blockquote></section>
    ${d.run ? readingBlock(d.run) : (inq.state === "inquiry_received" ? `<section class="block"><p class="hint">The copilot has not read this inquiry yet.</p></section>` : "")}
    ${replyBlock(d, dis)}
    ${openTasks.length ? `<section class="block"><h3>Open tasks</h3><ul class="tasks">${openTasks.map((t) => `<li>${esc(t.reason)}</li>`).join("")}</ul></section>` : ""}
    ${controlBlock(d, dis)}
    <section class="block"><h3>History</h3><ol class="timeline">${d.audit.map((e) => {
      const detail = eventDetail(e);
      return `<li><span class="when">${esc(fmtClock(e.at))}</span><span class="who">${esc(actorLabel(e.actor))}</span>` +
        `<span class="what">${esc(EVENT_LABEL[e.event_type] || e.event_type)}${detail ? `: ${esc(detail)}` : ""}</span></li>`;
    }).join("")}</ol></section>`;
}

/* ------------------------------------------------------------------ fact sheets */
async function renderFacts() {
  const units = await api("/api/units");
  $("#view-facts").innerHTML = units.map((u) => `<section class="unit">
    <h2>${esc(u.title)}</h2><p class="sub">${esc(u.district)}. Only verified facts can appear in a reply.</p>
    <table class="fact-table"><thead><tr><th scope="col">Fact</th><th scope="col">Value</th><th scope="col">Status</th><th scope="col">Source</th><th scope="col">Note</th></tr></thead>
    <tbody>${u.facts.map((f) => `<tr><td>${esc(f.label_en)}</td><td>${esc(f.value_en || f.value || "")}</td>
      <td><span class="status st-${esc(f.status)}">${esc(FACT_STATUS_LABEL[f.status] || f.status)}</span></td>
      <td>${esc(f.source_ref || "")}</td><td class="note">${esc(f.note || "")}</td></tr>`).join("")}</tbody></table></section>`).join("");
}

/* ------------------------------------------------------------------ loading */
async function loadDetail(id) {
  state.selected = id;
  state.detail = await api(`/api/inquiries/${encodeURIComponent(id)}`);
  renderList();
  renderDetail();
}

async function refresh() {
  state.inquiries = await api("/api/inquiries");
  if (!state.inquiries.some((i) => i.inquiry_id === state.selected)) state.selected = null;
  renderFilters();
  renderList();
  if (state.selected) await loadDetail(state.selected);
  else { state.detail = null; renderDetail(); }
  if (state.view === "facts") await renderFacts();
  for (const id of ["run-all", "add-inquiry", "reset-demo"]) {
    $(`#${id}`).disabled = !isOperator();
    $(`#${id}`).title = isOperator() ? "" : "Viewers can read but not change inquiries";
  }
}

async function act(fn, success) {
  try {
    const result = await fn();
    if (success) toast(typeof success === "function" ? success(result) : success);
    await refresh();
  } catch (error) {
    if (error.status === 422 && error.data && error.data.findings) { showOverride(error.data.findings); return; }
    toast(error.message, true);
  }
}

function showOverride(findings) {
  $("#override-slot").innerHTML = `<div class="override" role="alert">
    <p><strong>The checks block this text.</strong> Fix it, or approve with a written reason. The reason is kept in the history.</p>
    <ul>${findings.filter((f) => f.severity === "block").map((f) => `<li class="finding block-level">${esc(f.message)}</li>`).join("")}</ul>
    <label for="override-reason">Reason for approving anyway</label>
    <input id="override-reason" maxlength="300" placeholder="For example: parking price confirmed by the owner by phone today">
    <div><button class="btn btn-primary" data-action="override">Approve with this reason</button></div></div>`;
  $("#override-reason").focus();
}

/* ------------------------------------------------------------------ events */
function bindEvents() {
  $("#filters").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-filter]");
    if (!btn) return;
    state.filter = btn.dataset.filter;
    renderFilters();
    renderList();
  });
  $("#inquiry-list").addEventListener("click", async (e) => {
    const row = e.target.closest("[data-id]");
    if (!row) return;
    document.body.classList.add("show-detail");
    await loadDetail(row.dataset.id);
    $("#detail").focus();
  });
  $("#detail").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn || btn.disabled) return;
    const d = state.detail;
    const id = d && d.inquiry.inquiry_id;
    const draftId = d && d.draft && d.draft.draft_id;
    const text = () => ($("#draft-text") ? $("#draft-text").value : "");
    switch (btn.dataset.action) {
      case "back": document.body.classList.remove("show-detail"); break;
      case "process": act(() => api(`/api/inquiries/${id}/process`, { method: "POST" }),
        (out) => `Copilot finished: ${NEXT_ACTION_LABEL[out.next_best_action] || out.next_best_action}.`); break;
      case "approve": act(() => api(`/api/drafts/${draftId}/approve`, { method: "POST", body: { final_text: text() } }),
        "Approved. Send it from your mailbox, then mark it as sent."); break;
      case "override": act(() => api(`/api/drafts/${draftId}/approve`, {
        method: "POST", body: { final_text: text(), override_reason: $("#override-reason").value } }),
        "Approved with override. The reason is in the history."); break;
      case "reject": act(() => api(`/api/drafts/${draftId}/reject`, { method: "POST", body: {} }),
        "Draft rejected. This inquiry now needs your reply."); break;
      case "manual": act(() => api(`/api/inquiries/${id}/manual-reply`, { method: "POST", body: { text: text() } }),
        "Reply saved and checked. Review it once more, then approve."); break;
      case "copy": navigator.clipboard.writeText(d.draft.final_text || d.draft.text || "")
        .then(() => toast("Reply copied.")).catch(() => toast("Copy failed. Select the text instead.", true)); break;
      case "sent": act(() => api(`/api/inquiries/${id}/mark-sent`, { method: "POST" }), "Marked as sent."); break;
      case "accept": act(() => api(`/api/inquiries/${id}/accept-slot`, { method: "POST", body: { slot_id: btn.dataset.slot } }),
        "Viewing booked."); break;
      case "close": act(() => api(`/api/inquiries/${id}/close`, { method: "POST" }), "Inquiry closed."); break;
      case "stop":
        if (confirm("Stop all contact with this applicant? The copilot will not draft replies to them again.")) {
          act(() => api(`/api/inquiries/${id}/stop`, { method: "POST" }), "Contact stopped.");
        }
        break;
      case "erase":
        if (confirm("Erase this applicant's message and drafts? This cannot be undone. The history keeps only events without content.")) {
          act(() => api(`/api/inquiries/${id}/delete-data`, { method: "POST" }), "Applicant data erased.");
        }
        break;
      default: break;
    }
  });
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", async () => {
    state.view = tab.dataset.view;
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.toggle("is-active", t === tab);
      if (t === tab) t.setAttribute("aria-current", "page"); else t.removeAttribute("aria-current");
    });
    $("#view-inbox").hidden = state.view !== "inbox";
    $("#view-facts").hidden = state.view !== "facts";
    if (state.view === "facts") await renderFacts();
  }));
  $("#run-all").addEventListener("click", () => act(() => api("/api/inquiries/process-all", { method: "POST" }),
    (r) => (r.processed.length ? `Copilot read ${r.processed.length} new inquiries.` : "No new inquiries to read.")));
  $("#reset-demo").addEventListener("click", () => {
    if (confirm("Reset all demo data? Every change you made is lost.")) {
      state.selected = null;
      act(() => api("/api/demo/reset", { method: "POST" }), "Demo data reset.");
    }
  });
  $("#add-inquiry").addEventListener("click", async () => {
    const units = await api("/api/units");
    $("#add-unit").innerHTML = units.map((u) => `<option value="${esc(u.unit_id)}">${esc(u.title)}, ${esc(u.district)}</option>`).join("");
    $("#add-dialog").showModal();
  });
  $("#add-form").addEventListener("submit", (e) => {
    if (e.submitter && e.submitter.value === "cancel") return;
    e.preventDefault();
    const form = new FormData(e.target);
    const body = Object.fromEntries(form.entries());
    if (!body.contact_channel) body.contact_channel = null;
    act(async () => {
      const inquiry = await api("/api/inquiries", { method: "POST", body });
      $("#add-dialog").close();
      e.target.reset();
      state.selected = inquiry.inquiry_id;
      state.filter = "all";
      return inquiry;
    }, "Inquiry added. Run the copilot on it when ready.");
  });
  $("#user-select").addEventListener("change", async (e) => {
    state.user = state.users.find((u) => u.user_id === e.target.value);
    safeSet(USER_KEY, state.user.user_id);
    state.selected = null;
    document.body.classList.remove("show-detail");
    await refresh();
    toast(`Signed in as ${state.user.display_name}.`);
  });
}

async function init() {
  state.users = await (await fetch("/api/users")).json();
  const saved = safeGet(USER_KEY);
  state.user = state.users.find((u) => u.user_id === saved) || state.users.find((u) => u.role === "operator") || state.users[0];
  $("#user-select").innerHTML = state.users.map((u) =>
    `<option value="${esc(u.user_id)}" ${u.user_id === state.user.user_id ? "selected" : ""}>${esc(u.display_name)}</option>`).join("");
  const health = await api("/api/health");
  $("#provider").textContent = health.provider === "mock" ? "Copilot: mock rules, offline" : `Copilot: ${health.provider}`;
  bindEvents();
  await refresh();
}

init().catch((error) => toast(`Could not load the console: ${error.message}`, true));
