const MOD_API = "/api/moderator";

const modState = {
  cases: [],
  selected: null,
};

/** Plain-English mapping for internal cluster tags (rule_hits). */
const CLUSTER_TAG_PHRASES = {
  "cluster:age_question": "Someone asked how old another person is in a sensitive context",
  "cluster:minor_age_stated": "A young person’s age may have been stated",
  "cluster:adult_age_stated": "An adult’s age may have been stated alongside other risk cues",
  "cluster:parent_boundary": "Messages suggest worry about parents or approval",
  "cluster:secrecy_after_discomfort":
    "Secrecy or 'don't tell anyone' wording after uncomfortable topics",
  "cluster:advance_fee_gift_tax": "Conversation matches a gift-card / tax-refund style scam pattern",
  "cluster:crypto_double_scam":
    "Conversation matches a cryptocurrency doubling scam pattern",
  "cluster:job_upfront_fee_scam":
    "Conversation matches a job scam with upfront payment or wire requests",
  "cluster:pic_secrecy_pressure":
    "Image or photo requests combined with secrecy or pressure",
  "cluster:pic_request": "Strong pressure or requests for photos or images",
};

function tierDisplayName(tier) {
  if (tier === "high_risk") return "High risk";
  if (tier === "suspicious") return "Suspicious";
  if (tier === "safe") return "Safe";
  return tier ? String(tier).replace(/_/g, " ") : "Unknown";
}

function primaryDetectionSource(mlScore, ruleScore) {
  const m = Number(mlScore);
  const r = Number(ruleScore);
  const ml = Number.isFinite(m) ? m : 0;
  const rule = Number.isFinite(r) ? r : 0;
  const gap = 0.15;
  if (rule - ml >= gap && rule > 0.12) {
    return "Rule-based engine";
  }
  if (ml - rule >= gap && ml > 0.12) {
    return "ML classifier";
  }
  if (ml < 0.06 && rule < 0.06) {
    return "Automated scores are low — review messages and context";
  }
  return "Hybrid (ML and rules both contributed)";
}

function threatHitToPhrase(hit) {
  if (typeof hit !== "string") return null;
  if (hit.startsWith("cooccur:bomb+civic_target")) {
    return "Severe-threat wording may reference public or government targets";
  }
  if (hit.startsWith("cooccur:blowup+target")) {
    return "Severe-threat wording may reference buildings or crowded places";
  }
  if (hit.startsWith("phrase:")) {
    return "Wording flagged as potential threat or severe harm";
  }
  if (hit.startsWith("re:")) {
    return "Pattern suggesting serious harm or threats";
  }
  return null;
}

function collectTriggerPhrases(risk) {
  const seen = new Set();
  const out = [];

  function add(s) {
    if (!s || typeof s !== "string") return;
    const k = s.trim().toLowerCase();
    if (!k || seen.has(k)) return;
    seen.add(k);
    out.push(s.trim());
  }

  if (!risk) return out;

  const summary = risk.rule_trigger_summary;
  if (Array.isArray(summary)) {
    for (const line of summary) add(line);
  }

  const hits = risk.rule_hits;
  if (!hits || typeof hits !== "object") return out;

  const clusterKeys = [
    "age_disclosure_cluster",
    "scam_cluster",
    "image_pressure_cluster",
  ];
  for (const key of clusterKeys) {
    const arr = hits[key];
    if (!Array.isArray(arr)) continue;
    for (const tag of arr) {
      const phrase = CLUSTER_TAG_PHRASES[tag];
      if (phrase) add(phrase);
    }
  }

  const gs = hits.grooming_sequence;
  if (gs && typeof gs === "object") {
    if (gs.label === "grooming_high_confidence") {
      add("Grooming-style progression (flattery, isolation, or meet-up pressure)");
    } else if (Number(gs.score) >= 0.45) {
      add("Several grooming-related signals appeared across the thread");
    }
  }

  const threat = hits.threat;
  if (threat && typeof threat === "object") {
    const ts = Number(threat.threat_score);
    if (Number.isFinite(ts) && ts > 0.15) {
      const th = threat.threat_hits;
      if (Array.isArray(th)) {
        for (const h of th) {
          const p = threatHitToPhrase(h);
          if (p) add(p);
        }
      }
      const hadThreatLine = out.some((x) =>
        /threat|harm|severe|Pattern suggesting|public or government|buildings or crowded/i.test(x)
      );
      if (!hadThreatLine) {
        add("Threat or severe-harm wording detected");
      }
    }
  }

  const gp = hits.grooming_phrases;
  if (Array.isArray(gp) && gp.length) {
    add(`Grooming-related phrases matched (${gp.length} hit${gp.length === 1 ? "" : "s"})`);
  }

  const bk = hits.boundary_keywords;
  if (Array.isArray(bk) && bk.length) {
    add("High-risk boundary or contact-related keywords");
  }

  return out;
}

function renderFlagExplanation(caseRow) {
  const mount = el("flagExplanation");
  if (!caseRow) {
    mount.innerHTML = "";
    return;
  }

  const risk = caseRow.latest_risk;
  if (!risk) {
    mount.innerHTML = `
      <section class="mod-why-flagged" aria-labelledby="why-flagged-heading">
        <h3 id="why-flagged-heading" class="mod-why-flagged__title">Why it was flagged</h3>
        <p class="mod-why-flagged__empty">No automated risk snapshot is linked to this case yet. Use the chat view to read the conversation.</p>
      </section>`;
    return;
  }

  const tier = tierDisplayName(risk.tier);
  const finalS = Number(risk.final_score);
  const ruleS = Number(risk.rule_score);
  const mlS = Number(risk.ml_score);
  const finalStr = Number.isFinite(finalS) ? finalS.toFixed(2) : "—";
  const ruleStr = Number.isFinite(ruleS) ? ruleS.toFixed(2) : "—";
  const mlStr = Number.isFinite(mlS) ? mlS.toFixed(2) : "—";
  const source = primaryDetectionSource(risk.ml_score, risk.rule_score);
  const triggers = collectTriggerPhrases(risk);

  const triggersHtml =
    triggers.length > 0
      ? `<ul class="mod-why-flagged__triggers">${triggers
          .map((t) => `<li>${escapeHtml(t)}</li>`)
          .join("")}</ul>`
      : `<p class="mod-why-flagged__empty">No detailed triggers were recorded. Re-run analysis on the conversation if needed.</p>`;

  mount.innerHTML = `
    <section class="mod-why-flagged" aria-labelledby="why-flagged-heading">
      <h3 id="why-flagged-heading" class="mod-why-flagged__title">Why it was flagged</h3>
      <dl class="mod-why-flagged__dl">
        <div><dt>Tier</dt><dd>${escapeHtml(tier)}</dd></div>
        <div><dt>Final risk score</dt><dd class="mono">${escapeHtml(finalStr)}</dd></div>
        <div><dt>Rule score</dt><dd class="mono">${escapeHtml(ruleStr)}</dd></div>
        <div><dt>ML score</dt><dd class="mono">${escapeHtml(mlStr)}</dd></div>
        <div class="mod-why-flagged__dl--wide"><dt>Primary detection source</dt><dd>${escapeHtml(source)}</dd></div>
      </dl>
      <h4 class="mod-why-flagged__sub">Triggers</h4>
      ${triggersHtml}
    </section>`;
}

function renderModeratorTable() {
  const tbody = el("caseRows");
  tbody.innerHTML = "";

  for (const c of modState.cases) {
    const r = c.latest_risk;
    const riskStr = r ? `${r.tier} (${r.final_score})` : "-";
    const title = c.conversation_title || `Conv ${c.conversation_id}`;
    const pid = c.conversation_public_id || "";
    const wf = c.workflow_display || "Pending";
    const wfClass =
      wf === "Under review"
        ? "workflow-badge workflow-badge--review"
        : "workflow-badge workflow-badge--pending";

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="mono">${c.id}</td>
      <td>
        <div>${escapeHtml(title)}</div>
        <div class="mod-table__sub">
          #${c.conversation_id} ${escapeHtml(pid)}
        </div>
      </td>
      <td><span class="${wfClass}">${escapeHtml(wf)}</span></td>
      <td>${escapeHtml(c.source)}</td>
      <td>${c.priority}</td>
      <td>${escapeHtml(c.preview)}</td>
      <td class="mono">${escapeHtml(riskStr)}</td>
    `;
    tr.addEventListener("click", async () => {
      modState.selected = c;
      const detail = el("caseDetail");
      detail.hidden = false;
      renderFlagExplanation(c);
      try {
        const sr = await fetch(`${MOD_API}/cases/${c.id}/start-review`, {
          method: "POST",
        });
        if (!sr.ok) {
          console.warn("start-review", sr.status);
        }
      } catch (e) {
        console.warn(e);
      }
      await loadCases();
      modState.selected = modState.cases.find((x) => x.id === c.id) || c;
      renderFlagExplanation(modState.selected);
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
