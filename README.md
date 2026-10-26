# SocialScope AI — TikTok Analytics

SocialScope AI is an AI-powered social media intelligence dashboard for exploring TikTok comment sentiment, promotional language, repeated wording, and potential coordination indicators through transparent, explainable analysis.

This project is an independent educational portfolio project. It is not an official TikTok product and does not claim access to private TikTok data or production API integrations.

## Project overview

- Project name: SocialScope AI
- Platform label: TikTok Analytics
- Main heading: SocialScope AI
- Subtitle: TikTok Social Intelligence Platform
- Suggested GitHub repository name: `socialscope-ai-tiktok`

## Features

- Dashboard overview with empty states and summary metrics
- TikTok URL validation with honest status reporting
- CSV upload for TikTok-style comment data
- Explainable baseline sentiment analysis for Indonesian and English text
- Promotional keyword detection with clear limitations
- Duplicate and similar comment detection using TF-IDF and cosine similarity
- Potential coordination signal review without claiming proof of manipulation
- Simple export of summary metrics as CSV

## Architecture

- Frontend: React + Vite + Tailwind CSS
- Backend: Flask + pandas + scikit-learn
- Data analysis: lexicon baseline for sentiment and text similarity heuristics

## Local setup (Windows)

### 1) Create and activate a Python virtual environment

```powershell
cd "D:\WEB ALL\SocialScope-AI-TikTok"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) Start the backend API

```powershell
cd "D:\WEB ALL\SocialScope-AI-TikTok"
.\.venv\Scripts\Activate.ps1
python app.py
```

The Flask app runs at http://127.0.0.1:5000.

### 3) Start the frontend

```powershell
cd "D:\WEB ALL\SocialScope-AI-TikTok\frontend"
npm install
npm run dev
```

The Vite app runs at http://localhost:5173.

## API endpoints

### GET /api/health

Returns a basic health check.

Example response:

```json
{
  "status": "ok",
  "service": "SocialScope AI API"
}
```

### POST /api/analyze-csv

Uploads a CSV file and returns summary analysis metrics.

Required information:

- A CSV file with a comment column such as `comment`, `comments`, `text`, `content`, `comment_text`, `komentar`, or `teks`
- Optional columns: `timestamp`, `video_id`, and other metadata when available

Returns a JSON payload with:

- `summary`
- `sentiment`
- `repeated_comments`
- `similar_pairs`
- `hourly_activity`
- `coordination_signals`
- `findings`
- `method_notes`

### POST /api/analyze-url

Validates a TikTok URL and clearly states whether analysis is available.

Important behavior:

- It validates format and supported domains only.
- It does not scrape data or pretend comments were retrieved without an approved integration.
- It states when a real API connector is required.

## Limitations

- Sentiment scoring uses a transparent lexicon baseline instead of a trained production model.
- Promotional detection is keyword-based and is best treated as a signal, not confirmed advertising.
- Duplicate and similar-comment results are contextual indicators and do not prove coordinated behavior.
- This project does not claim access to private TikTok data or unauthorized scraping.
- Real-world TikTok analysis requires official API access, approval, and compliance review.

## Future improvements

- Add secure TikTok API integration with access validation
- Add a user-configurable keyword dictionary and scoring model
- Improve the sentiment pipeline with labeled Indonesian data and model evaluation
- Add robust export/reporting features for dataset quality and findings
- Add authentication and project-level user management for production deployments

## License

This project is for educational and portfolio use.
