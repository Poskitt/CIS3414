# AI-Driven Social Media Safety System

**Conversation-based harm detection prototype** for coursework and demos: a mock DM with **hybrid scoring** (ML + explainable rules), **three risk tiers**, and a **moderator queue**. Not connected to any live platform.

---

## Table of contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Project layout](#project-layout)
- [Train the classifier](#train-the-classifier)
- [Evaluation and tier tuning](#evaluation-and-tier-tuning)
- [Run the API and UI](#run-the-api-and-ui)
- [Synthetic data labels](#synthetic-data-labels)
- [PAN12 corpus (optional)](#pan12-corpus-optional)
- [Configuration](#configuration)
- [REST API](#rest-api)
- [Git and large files](#git-and-large-files)
- [Ethics and limitations](#ethics-and-limitations)

---

## Features

| Area | Details |
|------|---------|
| **ML leg** | TF-IDF + logistic regression, **probability calibration** (`CalibratedClassifierCV`), optional PAN12 + synthetic CSV training |
| **Rule leg** | High-precision patterns in [`app/pipeline/rules.py`](app/pipeline/rules.py): grooming sequences, age-disclosure clusters, scam / image-pressure clusters, threats |
| **Fusion** | Dynamic blend in [`app/pipeline/fusion.py`](app/pipeline/fusion.py): stronger rules when clusters fire; configurable fallbacks in [`app/config.py`](app/config.py) (default **0.6** ML / **0.4** rules) |
| **Tiers** | `safe` / `suspicious` / `high_risk` from fused score; optional send restriction and moderation cases |
| **UI** | Static frontend: chat + moderator pages (`frontend/`), served by FastAPI |

---

## Requirements

- **Python 3.11+** recommended.
- On **Python 3.14+**, prefer the **loose pins** in `requirements.txt` so pip can install a **prebuilt** scikit-learn wheel (a tight pin may try to build from source on Windows).

---

## Quick start

```powershell
git clone https://github.com/YOUR_USER/YOUR_REPO.git
cd YOUR_REPO

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# Train a model (synthetic-only is fastest)
python -m training.train_model --data synthetic

# Start server (Windows: port 8080 avoids common port-8000 issues)
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

Or double-click **`run_server.bat`** (activates `.venv` if present).

Open **http://127.0.0.1:8080/index.html** (chat) or **http://127.0.0.1:8080/moderator.html**. The chat page calls **`POST /api/bootstrap`** to seed users and demo conversations.

---

## Project layout

```
app/
  main.py              # FastAPI app + static frontend mount
  analysis.py          # Orchestrates ML + rules + fusion per conversation
  config.py            # Tier thresholds, fusion weights
  json_store.py        # JSON persistence (data/app_data.json)
  pipeline/
    rules.py           # Rule scores and clusters
    fusion.py          # Score fusion
    classifier.py      # joblib pipeline + severity mapping
    conversation_features.py
  routers/             # /api/chat, /api/moderator
frontend/              # HTML, CSS, JS
training/              # train_model.py, evaluate.py, datasets
data/                  # synthetic CSVs, optional safe/harmful CSVs, app_data.json (runtime)
```

Artifacts: trained model at **`app/ml_artifacts/calibrated_pipeline.joblib`** (create via training; not always committed).

---

## Train the classifier

From the **repository root**:

```powershell
# PAN12 folder present + synthetic (good for grooming + threat variety)
python -m training.train_model --data both

# Fast path: synthetic CSV only
python -m training.train_model --data synthetic

# PAN12 only (large XML)
python -m training.train_model --data pan12 --pan12-dir training\pan12-sexual-predator-identification-test-corpus-2012-05-21
```

**Useful flags:** `--max-negative-samples 60000` (default), `--max-features 20000`, `--min-df 2`, `--no-stratify` if stratified split fails. **`--balance` / `--no-balance`**: oversample minority classes on the train split (default: on). **`--extra-csvs` / `--no-extra-csvs`**: merge optional [`data/safe_conversations.csv`](data/safe_conversations.csv) (label 0) and [`data/harmful_conversations.csv`](data/harmful_conversations.csv) (`label` column) when present.

```powershell
python -m training.train_model --help
```

---

## Evaluation and tier tuning

After changing data or rules, run a **held-out validation** pass:

```powershell
python -m training.evaluate --data both

# Synthetic only, no extra CSV merge
python -m training.evaluate --data synthetic --no-extra-csvs

# Do not rewrite app/config.py
python -m training.evaluate --no-write-config
```

This prints metrics, compares tier cuts on **fused** scores, writes **`app/ml_artifacts/calibrated_pipeline.joblib`**, and by default updates **`tier_safe_max` / `tier_suspicious_max`** in [`app/config.py`](app/config.py). Re-run when the dataset or fusion logic changes.

---

## Run the API and UI

- **Storage:** [`data/app_data.json`](data/app_data.json) (v2 JSON). Delete the file to reset; set **`DATA_JSON_PATH`** to override the path.
- **Legacy:** v1 JSON is migrated on load. **`data/safety.db`** is not used by the current API.

**Windows:** use port **8080** if **8000** is blocked (`WinError 10013`).

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

**Optional:** [`commit_push.bat`](commit_push.bat) stages, prompts for a commit message, and runs `git push` (for local convenience).

---

## Synthetic data labels

[`data/synthetic_conversations.csv`](data/synthetic_conversations.csv) uses integer **`label`**:

| Label | Meaning |
|------:|---------|
| 0 | Harmless |
| 1 | Suspicious / grooming |
| 2 | Scam |
| 3 | Crime |
| 4 | Extremism |

The **UI/API** still expose three **tiers**. [`app/pipeline/classifier.py`](app/pipeline/classifier.py) maps class probabilities to a single **expected severity** in \[0, 1\], then **fuses** with the rule score.

**Regenerate** synthetic rows:

```powershell
python data\generate_synthetic_conversations.py --rows 500
python -m training.train_model --data synthetic
```

---

## PAN12 corpus (optional)

1. Obtain the **PAN12 Sexual Predator Identification** data per the task license (do **not** commit raw corpus to a public repo).
2. Place the bundle under:

   `training/pan12-sexual-predator-identification-test-corpus-2012-05-21/`

3. You need at least one **`*.xml`** conversation file and **`pan12-sexual-predator-identification-groundtruth-problem1.txt`** (predator author IDs). Training uses **Problem 1**: label **1** if any message author is in that list.

**Methods note:** Many public downloads are the **shared-task test** set, not a historically separate train split. Prefer an official **training** release for fitting if you have it, and document limitations in reports.

**Ethics:** Sensitive content. Do not redistribute; cite PAN12; use only in controlled coursework or research.

---

## Configuration

| Setting | Location |
|---------|----------|
| Tier boundaries (`tier_safe_max`, `tier_suspicious_max`) | [`app/config.py`](app/config.py) |
| Default fusion weights (`ml_weight`, `rule_weight`) | [`app/config.py`](app/config.py) |
| Data file path | Env **`DATA_JSON_PATH`** |

---

## REST API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/bootstrap` | Seed users + demo conversations |
| POST | `/api/send_message` | Append message; run pipeline |
| GET | `/api/conversations` | Conversation summaries |
| GET | `/api/conversations/{id}` | Thread + latest risk |
| POST | `/api/conversations/{id}/analyze` | Re-run pipeline |
| POST | `/api/conversations/{id}/flag` | User report |
| GET | `/api/moderator/conversations` | Open cases |
| POST | `/api/moderator/cases/{id}/dismiss` | Clear restriction + close case |
| POST | `/api/moderator/cases/{id}/confirm` | Confirm + keep restriction |

---

## Git and large files

- **PAN12** and other large corpora are listed in [`.gitignore`](.gitignore) (e.g. `training/pan12-*/`). Clone the repo, then add data **locally**; do not push multi-hundred-MB XML to GitHub.
- If a large file was committed by mistake, rewrite history (e.g. orphan branch or `git filter-repo`) before pushing; GitHub rejects blobs **> 100 MB**.

---

## Ethics and limitations

Educational **prototype** only. Expect **false positives and false negatives**. **Human review** is required for any real moderation workflow. Discuss **bias**, **class imbalance**, and **data sources** (synthetic templates vs. real distributions) in coursework or documentation.
