# Smart Market Watchlist 📈

> **Catch up on what moved while you were away — powered by context-aware market change detection.**

Smart Market Watchlist is a full-stack financial application that eliminates stock market noise. Instead of bombarding investors with raw tick-by-tick prices, it analyzes how your watchlist stocks performed relative to the benchmark index (**NIFTY 50**) and their respective industry sectors since you last checked.

---

## 🌟 Key Features

- **"What I Missed" Dashboard**: Categorizes stocks into three clear action buckets based on away-period returns:
  - 🚨 **Needs Your Attention**: Significant moves, volume anomalies, or strong relative index divergence.
  - 👁️ **Worth Watching**: Moderate moves or sector-aligned momentum.
  - 🟢 **All Quiet**: Stocks performing within normal volatility bounds.
- **Full-Screen WebGL Landing**: An immersive animated wave background (`GradientWaves` via OGL) presenting a clean, editorial start screen.
- **Stock Detail Drawer**: Progressive disclosure right panel showing:
  - 📊 Stock return vs. **NIFTY 50** return over the exact away period.
  - 🏭 **Sector Performance**: Real-time comparison against sector constituents, plain-English takeaway, and curated sector peers.
  - 🔊 **Volume Activity Metrics**: Current session volume vs 5-day, 20-day, and 60-day moving averages.
  - 📰 **Live News**: Relevant headlines pulled via Yahoo Finance.
  - 📉 **7-Day Price Sparklines**: Contextual historical trend leading up to the latest completed trading session.
- **Substantially Expanded Stock Catalog & Multi-Attribute Search**: Browse 50+ real, liquid NSE-listed equities across 13 sectors (Technology, Banking, Financial Services, Automotive, Pharma, Healthcare, Energy, FMCG, Metals, Telecom, Construction, Industrials, Consumer Goods) with search by ticker, company name, or common sector aliases (`IT`, `Tech`, `Auto`, `Pharma`, `Finance`).
- **Strict Timestamp Separation**: Clearly separates the user's actual **"Last checked"** timestamp from the **"Latest market data"** timestamp displayed in IST (`Asia/Kolkata`), providing clear market-closed banners when checking after hours or on weekends.
- **Clickable Hero Navigation**: Smooth-scrolling jump links from top summary cards to destination sections with brief visual pulse highlights.

---

## 🧠 Meaningful-Change Detection Engine

The change detection engine (`change_detection.py`) measures away-period price changes against historical volatility and market benchmark movements:

1. **User Checkpoint Resolution**: Pinpoints the exact timestamp of the user's last check or manual acknowledgement.
2. **Benchmark Alignment**: Pairs stock price returns against NIFTY 50 (`^NSEI`) over the matching trading window.
3. **Volatility Normalization**: Calculates z-scores (`unusualness_z`) comparing recent return magnitude against the stock's historical period volatility.
4. **Market Schedule Awareness**: Recognizes National Stock Exchange of India (NSE) trading sessions (Mon–Fri 09:15–15:30 IST) to prevent reporting zero-move false alarms during weekends or off-hours.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, Flask 3.x, SQLite (WAL mode), pandas, yfinance.
- **Frontend**: React 19, Vite, Vanilla CSS Design System (warm cream aesthetic, frosted glass glassmorphism, restrained typography), OGL (WebGL rendering).
- **CI/CD**: GitHub Actions.

---

## 📁 Project Structure

```text
Watchlist/
├── .github/
│   └── workflows/
│       └── ci.yml                      # GitHub Actions CI workflow
├── backend/
│   ├── api.py                          # Flask REST API routes & serialization
│   ├── change_detection.py             # Volatility & relative performance engine
│   ├── database.py                     # SQLite connection & auto-schema migration
│   ├── market_data.py                  # yfinance service, stock catalog & sector peers
│   ├── repository.py                   # Data access layer for users & watchlists
│   ├── requirements.txt                # Python package dependencies
│   └── test_*.py                       # Backend unit test suite (49 tests)
└── frontend/
    ├── package.json                    # Node dependencies & build scripts
    ├── vite.config.js                  # Vite builder configuration
    └── src/
        ├── App.jsx                     # Main dashboard & drawer UI
        ├── GradientWaves.jsx           # OGL WebGL animated start screen
        ├── styles.css                  # Custom CSS design system
        └── lib/
            └── api.js                  # API client with environment base URL
```

---

## 🚀 Local Setup & Running Instructions

### Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: 20.x or higher
- **npm**: 9.x or higher

### 1. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start Flask API server (runs on http://127.0.0.1:5000)
python api.py
```

### 2. Frontend Setup
```bash
# Open a second terminal and navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite dev server (runs on http://localhost:5173)
npm run dev
```

### 3. Accessing the Application
Open your web browser and navigate to **`http://localhost:5173`**.

### 4. Running the Backend Test Suite
```bash
# Run the complete backend test suite (from repository root)
python -m unittest discover -s backend -t backend
```

### 5. Building the Frontend for Production
```bash
# Navigate to frontend directory and build static assets
cd frontend
npm run build
```
Outputs static production assets into `frontend/dist/`.

### 📌 Important Notes
- **Automatic Database Initialization**: The SQLite database (`watchlist.db`) is automatically created with all required tables when the backend starts. No pre-existing database file is required.
- **Market Data & Offline Schedule**: Market data is fetched dynamically via `yfinance`. Outside active NSE market hours (Mon–Fri 09:15–15:30 IST) or on weekends, the system cleanly displays the latest completed trading session alongside explicit market-status banners.

---

## 🧪 Testing & Verification

The project includes a comprehensive backend unit test suite covering market schedule checks, relative change calculations, catalog search, persistence, and REST API endpoints.

```bash
# Run the complete backend test suite (from root)
python -m unittest discover -s backend -t backend
```
- **Test Results**: **49 / 49 PASSED** (0 failures, 0 errors).

---

## 📦 Frontend Production Build

To verify or generate the static production bundle:

```bash
cd frontend
npm run build
```
Outputs optimized HTML/CSS/JS artifacts inside `frontend/dist/`.

---

## ⚙️ GitHub Actions CI

Continuous Integration is configured via `.github/workflows/ci.yml`. On every `push` or `pull_request` to `main`, CI automatically:
1. Sets up Python 3.11 and installs `backend/requirements.txt`.
2. Runs the full backend test suite (`python -m unittest discover -s backend -t backend`).
3. Sets up Node.js 20, runs `npm ci`, and verifies `npm run build`.

---

## 🛡️ Market Data Limitations & Resilience

- **yfinance Rate Limits & Delays**: Uses local SQLite/memory caching and fallback handling for rate-limited symbol queries.
- **Off-Market Hours**: Automatically detects closed market sessions and displays completed session data alongside explicit market-status indicators.
- **Unlisted Symbols**: Employs heuristic fallback sector classification for non-catalog equities.

---

## 🌐 Deployment Status

Production deployment is **not configured yet**. The application runs locally or can be deployed to cloud hosts (e.g., Render, Railway, Vercel) by pointing `VITE_API_BASE_URL` to the hosted backend instance.

---

## ⚠️ Disclaimer

*This application is built strictly for demonstration and educational purposes. Market data is sourced from public endpoints and may be delayed. Content produced by this tool does **NOT** constitute financial or investment advice.*
