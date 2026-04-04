# Social messaging safety prototype

Standalone mock DM with **conversation-level** hybrid scoring: **TF-IDF + logistic regression**, **probability calibration** (`CalibratedClassifierCV`, sigmoid), **dynamic fusion** (rule-heavy when grooming clusters / strong rules fire; ML-heavy when the model is very confident; slight downward nudge when both legs are quiet), plus **conversation feature text** appended for the ML leg only. Default weights **0.6 / 0.4** are fallbacks in `app/config.py`. **Tier cuts** `tier_safe_max` / `tier_suspicious_max` can be tuned from a held-out validation set via `python -m training.evaluate` (updates the marked block in `app/config.py`). Tiers: `safe` / `suspicious` / `high_risk`, moderator queue, optional send restriction on high risk.

Not connected to Instagram or any live platform.

## Requirements

- **Python 3.11+** recommended. On **Python 3.14+**, use the loose pins in `requirements.txt` so pip can install a **prebuilt** `scikit-learn` wheel (pinned `1.5.2` may try to compile from source on Windows).

## Setup

```powershell
cd p:\CIS_Complex_Systems
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m training.train_model --help
```

### Train the classifier

From the project root:

```powershell
# Default: PAN12 (if present) + synthetic CSV — recommended for demos that need both grooming + threat examples
python -m training.train_model --data both

# Synthetic CSV only (fast)
python -m training.train_model --data synthetic

# PAN12 test corpus only (large XML; see below)
python -m training.train_model --data pan12 --pan12-dir training\pan12-sexual-predator-identification-test-corpus-2012-05-21
```

Useful flags: `--max-negative-samples 60000` (default), `--max-features 20000`, `--min-df 2` (optional for noisy corpora), `--no-stratify` if stratified split fails. **`--balance` / `--no-balance`**: oversample minority classes on the train split (default: on). **`--extra-csvs` / `--no-extra-csvs`**: merge optional **`data/safe_conversations.csv`** (all treated as label 0) and **`data/harmful_conversations.csv`** (uses `label` column) when those files exist.

### Evaluation + tier threshold tuning

After training data or rules change, run a **held-out 20% validation** pass that prints accuracy, per-class metrics, confusion matrix, compares **old vs tuned** tier cuts on **fused** scores, saves **`app/ml_artifacts/calibrated_pipeline.joblib`**, and (by default) rewrites the auto-tier block in **`app/config.py`**:

```powershell
python -m training.evaluate --data both
# Synthetic only, skip optional CSV merge:
python -m training.evaluate --data synthetic --no-extra-csvs
# Do not patch config.py:
python -m training.evaluate --no-write-config
```

Thresholds are **data-dependent**; re-run when the dataset or fusion logic changes.

After you change **`data/synthetic_conversations.csv`**, **PAN12 files**, **`data/safe_conversations.csv`**, **`data/harmful_conversations.csv`**, or **`app/pipeline/rules.py`**, re-run training (and optionally **evaluate**), then restart the API.

### Synthetic CSV labels (multi-class)

`data/synthetic_conversations.csv` uses integer **`label`**:

| Label | Meaning |
|------:|---------|
| 0 | Harmless |
| 1 | Suspicious / grooming |
| 2 | Scam |
| 3 | Crime |
| 4 | Extremism |

The **API still exposes** three **tiers** (`safe` / `suspicious` / `high_risk`). The trained classifier outputs class probabilities; [`app/pipeline/classifier.py`](p:\CIS_Complex_Systems\app\pipeline\classifier.py) maps them to a single **expected severity** in \([0,1]\), then **fuses** with the rule score as before.

**Regenerate** a larger balanced set (slang, typos, edge cases like jokes-as-harmless):

```powershell
python data\generate_synthetic_conversations.py --rows 500
python -m training.train_model --data synthetic
```

For coursework: add **hard negatives** (sarcasm, ambiguous intent) by hand; pure templates can yield **optimistic** validation scores.

### PAN12 (Sexual Predator Identification, 2012)

Place the official bundle under:

`training/pan12-sexual-predator-identification-test-corpus-2012-05-21/`

You need at least one `*.xml` conversation file and **`pan12-sexual-predator-identification-groundtruth-problem1.txt`** (predator author IDs). Training uses **Problem 1**: label **1** if any message author appears in that list.

**Methodology:** The usual download is the **shared-task test corpus**. Training on it means you are not using a historically separate train split; state that limitation in your report. Prefer the official **training** release for `fit` and reserve this XML for evaluation if you can obtain it.

**Ethics:** Raw chats are sensitive. Do not redistribute; cite PAN12; use only in a controlled coursework / research setting.

## Run API + static UI

From the **project root** (so `data/app_data.json` is created next to your other `data/` files).

Chats, users, messages, risk rows, and moderation cases are stored in **`data/app_data.json`** as **version 2 JSON** (indented for readability; array rows instead of repeating long field names on every message/risk row; conversation members are `member_ids` on each conversation). Older **version 1** verbose files are still read and migrated automatically. Reset by deleting the file and calling bootstrap again. Override the path with env **`DATA_JSON_PATH`**. The old SQLite file **`data/safety.db`** is no longer used by the API.

**Windows:** Port **8000** is often reserved or blocked (`WinError 10013`). Use **8080** (or another free port) every time:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

Or double-click **`run_server.bat`** (same command, activates `.venv` if present).

- Chat: `http://127.0.0.1:8080/index.html`
- Moderator: `http://127.0.0.1:8080/moderator.html`

`POST /api/bootstrap` runs automatically from the chat page.

## Training data

- **`data/synthetic_conversations.csv`** — short synthetic threads (grooming / safe / threat-style lines for the hybrid demo).
- **`training/pan12_dataset.py`** — streams the PAN12 XML (Problem 1 labels); see **Train the classifier** above.
- In your report, discuss **class imbalance**, **segmentation**, **bias**, and **false positives** for both sources.

## Ethics

Prototype for education. Expect false positives. Human review is mandatory for any real deployment.

## API summary

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/bootstrap` | Seed demo users + conversation |
| POST | `/api/send_message` | Append message; run pipeline |
| GET | `/api/conversations/{id}` | Thread + latest risk |
| POST | `/api/conversations/{id}/analyze` | Re-run pipeline |
| POST | `/api/conversations/{id}/flag` | User report |
| GET | `/api/moderator/conversations` | Open cases |
| POST | `/api/moderator/cases/{id}/dismiss` | Clear restriction + close case |
| POST | `/api/moderator/cases/{id}/confirm` | Confirm + keep restriction |
