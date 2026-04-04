const API_BASE = "/api";

const state = {
  conversationId: null,
  users: [],
  conversations: [],
};

function tierKey(t) {
  if (t === "high_risk") return "high_risk";
  if (t === "suspicious") return "suspicious";
  return "safe";
}

function renderRisk(risk) {
  const labelEl = el("riskLabel");
  const banner = el("riskBanner");
  const modal = el("safetyModal");

  if (!risk) {
    labelEl.textContent = "";
    banner.classList.remove("is-visible", "risk-banner--high");
    return;
  }

  const pillClass = `risk-pill risk-pill--${tierKey(risk.tier)}`;
  labelEl.innerHTML = `
    Risk:
    <span class="${pillClass}">${escapeHtml(risk.tier)}</span>
    <span class="mono muted">(${escapeHtml(String(risk.final_score))})</span>
  `;

  if (risk.tier === "suspicious") {
    banner.textContent = "Heads up: this thread looks suspicious.";
    banner.classList.add("is-visible");
    banner.classList.remove("risk-banner--high");
  } else if (risk.tier === "high_risk") {
    banner.textContent = "High risk: messaging may be restricted.";
    banner.classList.add("is-visible", "risk-banner--high");
    modal.classList.add("is-visible");
    modal.setAttribute("aria-hidden", "false");
  } else {
    banner.classList.remove("is-visible", "risk-banner--high");
  }
}

function tierScoreClass(tier) {
  if (!tier) return "chat-list__score chat-list__score--none";
  if (tier === "high_risk") {
    return "chat-list__score chat-list__score--high_risk";
  }
  if (tier === "suspicious") {
    return "chat-list__score chat-list__score--suspicious";
  }
  return "chat-list__score chat-list__score--safe";
}

function formatListScore(finalScore) {
  if (finalScore == null || finalScore === "") return "n/a";
  const n = Number(finalScore);
  if (Number.isNaN(n)) return "n/a";
  return n.toFixed(4);
}

function renderChatList() {
  const ul = el("chatList");
  ul.innerHTML = "";

  for (const c of state.conversations) {
    const li = document.createElement("li");
    li.className = "chat-list__item";
    if (c.id === state.conversationId) {
      li.classList.add("is-active");
    }
    const scoreText = formatListScore(c.latest_final_score);
    const scoreClass = tierScoreClass(c.latest_tier);
    li.innerHTML = `
      <div>${escapeHtml(c.title)}</div>
      <div class="chat-list__sub">#${c.id}
        <span class="${scoreClass}" title="Latest fused risk score">${escapeHtml(scoreText)}</span>
      </div>
      <div class="chat-list__sub">${escapeHtml(c.last_preview)}</div>
    `;
    li.addEventListener("click", () => {
      state.conversationId = c.id;
      renderChatList();
      refresh();
    });
    ul.appendChild(li);
  }
}

function renderThread(data) {
  el("convTitle").textContent = data.title || "Chat";
  el("convPublicId").textContent =
    "public_id: " + (data.public_id || "n/a");

  const thread = el("thread");
  thread.innerHTML = "";

  for (const m of data.messages || []) {
    const u = state.users.find((x) => x.id === m.sender_id);
    const name = u ? u.username : `user ${m.sender_id}`;
    const div = document.createElement("div");
    div.className = "thread__msg";
    div.innerHTML = `
      <div class="thread__meta">${escapeHtml(name)}</div>
      <div>${escapeHtml(m.content)}</div>
    `;
    thread.appendChild(div);
  }

  thread.scrollTop = thread.scrollHeight;
  renderRisk(data.latest_risk);

  const note = el("restrictNote");
  note.textContent = data.send_restricted
    ? "Sending restricted until moderator dismisses."
    : "";
}

async function refresh() {
  if (state.conversationId == null) return;

  const [listRes, threadRes] = await Promise.all([
    fetch(`${API_BASE}/conversations`),
    fetch(`${API_BASE}/conversations/${state.conversationId}`),
  ]);

  if (!listRes.ok || !threadRes.ok) {
    throw new Error("load");
  }

  state.conversations = await listRes.json();
  renderChatList();
  renderThread(await threadRes.json());
}

async function bootstrap() {
  const res = await fetch(`${API_BASE}/bootstrap`, { method: "POST" });
  if (!res.ok) throw new Error("bootstrap");

  const data = await res.json();
  state.conversationId = data.conversation_id;
  state.users = data.users;
  state.conversations = data.conversations || [];

  const sel = el("userSelect");
  sel.innerHTML = "";

  for (const u of data.users.filter((x) => x.role !== "moderator")) {
    const opt = document.createElement("option");
    opt.value = String(u.id);
    opt.textContent = u.username;
    sel.appendChild(opt);
  }

  const mod = data.users.find((x) => x.role === "moderator");
  if (mod) {
    const opt = document.createElement("option");
    opt.value = String(mod.id);
    opt.textContent = `${mod.username} (moderator)`;
    sel.appendChild(opt);
  }

  renderChatList();
  await refresh();
}

async function send() {
  const text = el("input").value.trim();
  if (!text) return;

  const senderId = Number(el("userSelect").value);
  const res = await fetch(`${API_BASE}/send_message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: state.conversationId,
      sender_id: senderId,
      content: text,
    }),
  });

  if (!res.ok) {
    let detail = {};
    try {
      detail = await res.json();
    } catch {
      /* ignore */
    }
    alert(detail.detail || res.statusText);
    return;
  }

  el("input").value = "";
  const data = await res.json();
  await refresh();
  if (data.risk) renderRisk(data.risk);
}

async function reanalyze() {
  const res = await fetch(
    `${API_BASE}/conversations/${state.conversationId}/analyze`,
    { method: "POST" }
  );
  if (!res.ok) {
    alert("Analyze failed");
    return;
  }
  await refresh();
}

async function report() {
  const res = await fetch(
    `${API_BASE}/conversations/${state.conversationId}/flag`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "user", reason: "user_report_ui" }),
    }
  );
  if (!res.ok) {
    alert("Flag failed");
    return;
  }
  alert("Reported to moderator queue.");
}

async function newChat() {
  const title = prompt("Title for the new chat (optional):", "");
  const res = await fetch(`${API_BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title || null }),
  });
  if (!res.ok) {
    alert("Could not create chat");
    return;
  }
  const summary = await res.json();
  state.conversationId = summary.id;
  await refresh();
}

function aliceBobIds() {
  const alice = state.users.find((u) => u.username === "alice");
  const bob = state.users.find((u) => u.username === "bob");
  if (alice && bob) return [alice.id, bob.id];

  const regular = state.users
    .filter((u) => u.role === "user")
    .sort((x, y) => x.id - y.id);
  if (regular.length >= 2) return [regular[0].id, regular[1].id];
  return regular.map((u) => u.id);
}

function cycleAliceBob() {
  const ids = aliceBobIds();
  if (ids.length < 2) return;

  const sel = el("userSelect");
  const cur = Number(sel.value);
  const i = ids.indexOf(cur);
  sel.value = String(ids[(i + 1) % ids.length]);
}

function onComposerKeydown(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
    return;
  }
  if (e.key === "Tab") {
    e.preventDefault();
    cycleAliceBob();
  }
}

function closeSafetyModal() {
  const modal = el("safetyModal");
  modal.classList.remove("is-visible");
  modal.setAttribute("aria-hidden", "true");
}

function initChatPage() {
  el("input").addEventListener("keydown", onComposerKeydown);
  el("send").addEventListener("click", send);
  el("refresh").addEventListener("click", refresh);
  el("analyze").addEventListener("click", reanalyze);
  el("report").addEventListener("click", report);
  el("newChat").addEventListener("click", newChat);
  el("modalDismiss").addEventListener("click", closeSafetyModal);
  el("modalReport").addEventListener("click", async () => {
    await report();
    closeSafetyModal();
  });

  bootstrap().catch((err) => {
    console.error(err);
    alert("Start API: python -m uvicorn app.main:app --reload");
  });
}

document.addEventListener("DOMContentLoaded", initChatPage);
