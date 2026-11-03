# SocialScope AI — TikTok Analytics

**TikTok Social Intelligence Platform**

An AI-powered platform for exploring TikTok comment sentiment, promotional patterns, and potential coordinated activity through data-driven analysis.

> **Independent, unofficial project.** Built for education and as an AI engineering portfolio piece. It is not affiliated with, endorsed by, or connected to TikTok or ByteDance.

Suggested repository name: `socialscope-ai-tiktok`

## What it does

| Area | Behaviour |
|---|---|
| **CSV comment analysis** | Upload a CSV; everything on screen is computed from that file. With no upload, every page shows an empty state. No sample or fabricated numbers exist anywhere. |
| **Sentiment (Indonesian)** | Rule-based **lexicon baseline** (not a trained model): positive / neutral / negative, with negation, intensifiers, slang and emoji handling. Each label lists the words that caused it. |
| **Promotional signals** | Configurable keyword categories plus link and phone-number patterns. Output says *why* a comment was flagged and is labelled a **signal, not confirmed advertising**. |
| **Repeated / similar comments** | Exact duplicates, duplicates after normalization, TF-IDF + cosine-similarity groups, and repeated 3–4 word phrases. |
| **Potential coordination indicators** | Repeated-text share, posting-time bursts (needs timestamps), repeated text inside bursts, same text across video IDs (needs `video_id`). Presented as **indicators, not proof**. No account is ever named or accused. |
| **TikTok URL check** | Validates the URL format and domain only. Reports honestly that **no comments are retrieved** because no authorized API connector is configured. No scraping. |
| **Reports** | Dataset-quality table, limitations, and CSV export (comment results and summary). |

## Project structure

```
socialscope-ai-tiktok/
├── backend/
│   ├── app.py                  Flask app factory and routes
│   ├── config.py               Environment-based settings
│   ├── requirements.txt
│   ├── .env.example
│   ├── analysis/
│   │   ├── preprocessing.py    CSV loading, validation, normalization, PII masking
│   │   ├── sentiment.py        Lexicon baseline + optional evaluation on your labels
│   │   ├── promo.py            Promotional signal detection
│   │   ├── similarity.py       Duplicates, TF-IDF/cosine groups, repeated phrases
│   │   ├── coordination.py     Exploratory coordination indicators
│   │   ├── pipeline.py         Orchestration and response building
│   │   └── errors.py
│   ├── integrations/tiktok.py  URL validation + CommentSource interface (unconfigured)
│   └── tests/test_api.py       pytest suite
├── frontend/
│   ├── src/{App.jsx, api.js, utils.js, components/, pages/}
│   ├── vite.config.js          Dev server proxies /api to Flask
│   └── tailwind.config.js
├── scripts/                    Windows helper scripts
└── README.md
```

## Setup on Windows

**Requirements:** Python 3.10+ (tick "Add Python to PATH" in the installer) and Node.js 18+ (LTS). Check with `python --version` and `node --version`.

### 1. Backend (PowerShell, terminal 1)

```powershell
cd socialscope-ai-tiktok\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

The API runs at `http://127.0.0.1:5000`. Check it by opening `http://127.0.0.1:5000/api/health`.

If PowerShell blocks `Activate.ps1` with an execution-policy error, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use Command Prompt and `.venv\Scripts\activate.bat`.

### 2. Frontend (PowerShell, terminal 2)

```powershell
cd socialscope-ai-tiktok\frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The dev server proxies `/api` to the backend, so no CORS setup is needed.

### Shortcut

Double-click `scripts\start-backend.bat` and `scripts\start-frontend.bat` (each opens its own window; the first run installs dependencies).

### Tests and production build

```powershell
cd backend ; .\.venv\Scripts\Activate.ps1 ; python -m pytest -q
cd ..\frontend ; npm run build
```

## CSV format

| Column | Required | Notes |
|---|---|---|
| `comment` | **yes** | Also accepted: `text`, `komentar`, `comment_text`, `content` |
| `timestamp` | no | ISO dates, common date formats, or Unix seconds/milliseconds. Needed for time analysis (≥ 20 parseable values). |
| `video_id` | no | Needed for the cross-video indicator (≥ 2 videos). |
| `label` | no | Your own `positive` / `neutral` / `negative` labels. If present, baseline accuracy is computed on them. |
| `username` | no | **Ignored.** Never analysed, returned or exported. |

Comma, semicolon, tab and pipe delimiters are detected from the header. Limits (configurable in `backend/.env`): 5 MB and 5,000 comments per file. Rows with more fields than the header (often an unquoted comma inside a comment) are skipped and counted, never silently truncated.

## API

All responses share one envelope. Success: `{"ok": true, "data": {...}}`. Error: `{"ok": false, "error": {"code": "...", "message": "...", "details": {...}}}`.

| Method & path | Purpose | Notable errors |
|---|---|---|
| `GET /api/health` | Status, limits, integration status | — |
| `GET /api/methodology` | Methods, keyword categories, limitations | — |
| `POST /api/analyze-csv` | `multipart/form-data`: `file` (.csv), optional `similarity_threshold` (0.50–0.99) | 400 missing file or bad parameter · 413 too large / too many rows · 415 not `.csv` · 422 empty file, missing `comment` column, no usable rows |
| `POST /api/analyze-url` | JSON `{"url": "..."}` | 400 bad request body · 422 invalid or unsupported URL |

`/api/analyze-url` returns `analysis_status: "validated_only"`, `content_analyzed: false` and `comments_retrieved: 0` for every valid URL, and includes the connector status.

## Privacy and safety choices

- Usernames are not needed and are dropped on load.
- Emails, phone numbers and `@mentions` are masked in displayed and exported text, and never appear in repeated-phrase output.
- Uploaded files are processed in memory and not stored. The browser keeps results in the open tab only.
- Exports escape cells that start with `= + - @` to prevent spreadsheet formula injection.
- No account is labelled a bot or buzzer.

## Limitations

- **Sentiment is a lexicon baseline.** It cannot detect sarcasm, understands little context, and has a small vocabulary. No accuracy is claimed. Accuracy is reported only when your CSV has a `label` column, and a small labelled sample gives unstable numbers.
- **Promotional signals** are keyword and pattern matches and will include false positives (and miss unlisted wording).
- **Similarity and repeats** often reflect trends, memes or catchphrases.
- **Coordination indicators** are statistics about one file, not proof of coordinated behaviour.
- **No automatic retrieval.** Pasting a URL cannot fetch comments, because no authorized TikTok API connector exists in this project. Provide a CSV you are permitted to analyse.
- Size is capped at 5,000 comments because similarity grouping grows quickly with row count.
- Python-side tests cover the analysis and API; the UI was exercised in a real browser (see below) but there is no automated frontend test suite yet.

## Adding a real data source later

Implement `CommentSource` in `backend/integrations/tiktok.py` (`status()` and `fetch_comments()`), return it from `get_connector()`, then have `/api/analyze-url` feed its comments into `analysis.pipeline`. Use only an API and permissions you are authorized to use, and keep tokens in `backend/.env` (never committed).

## Future improvements

Evaluate an Indonesian transformer model (e.g. IndoBERT) against the baseline on labelled data · a labelled Indonesian test set and evaluation report · language detection for mixed-language comments · background jobs for larger files · automated frontend tests.
