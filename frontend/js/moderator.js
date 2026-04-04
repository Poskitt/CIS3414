/**
 * Moderator queue — list open cases, dismiss or confirm with optional note.
 */

const MOD_API = "/api/moderator";

const modState = {
  cases: [],
  selected: null,
};

function renderModeratorTable() {
  const tbody = el("caseRows");
  tbody.innerHTML = "";

  for (const c of modState.cases) {
    const r = c.latest_risk;
    const riskStr = r ? `${r.tier} (${r.final_score})` : "—";
    const title = c.conversation_title || `Conv ${c.conversation_id}`;
    const pid = c.conversation_public_id || "";

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="mono">${c.id}</td>
      <td>
        <div>${escapeHtml(title)}</div>
        <div class="mod-table__sub">
          #${c.conversation_id} ${escapeHtml(pid)}
        </div>
      </td>
      <td>${escapeHtml(c.source)}</td>
      <td>${c.priority}</td>
      <td>${escapeHtml(c.preview)}</td>
      <td class="mono">${escapeHtml(riskStr)}</td>
    `;
    tr.addEventListener("click", () => {
      modState.selected = c;
      const detail = el("caseDetail");
      detail.hidden = false;
      el("caseJson").textContent = JSON.stringify(c, null, 2);
    });
    tbody.appendChild(tr);
  }
}

async function loadCases() {
  const res = await fetch(`${MOD_API}/conversations`);
  if (!res.ok) {
    alert("load failed");
    return;
  }
  modState.cases = await res.json();
  renderModeratorTable();
}

async function moderatorAction(path) {
  if (!modState.selected) return;

  const note = prompt("Moderator note (optional):", "") ?? "";
  const res = await fetch(
    `${MOD_API}/cases/${modState.selected.id}/${path}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: note || null }),
    }
  );

  if (!res.ok) {
    alert("failed");
    return;
  }

  modState.selected = null;
  el("caseDetail").hidden = true;
  await loadCases();
}

function closeCaseDetail() {
  modState.selected = null;
  el("caseDetail").hidden = true;
}

function initModeratorPage() {
  el("dismiss").addEventListener("click", () => moderatorAction("dismiss"));
  el("confirm").addEventListener("click", () => moderatorAction("confirm"));
  el("closeDetail").addEventListener("click", closeCaseDetail);

  loadCases().catch(() => alert("Start API"));
}

document.addEventListener("DOMContentLoaded", initModeratorPage);
