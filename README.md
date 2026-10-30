# Nimbus Financial Intelligence

## Overview

Nimbus is a Streamlit dashboard for exploring public company financial data. It retrieves market, statement, news, and analyst information from Yahoo Finance through `yfinance`. Local use still requires an internet connection for those data requests.

The app can run locally or be deployed to AWS with the CloudFormation template in `scripts/nimbus-aws.yaml`.
The demo has no login or user separation: search history is shared by everyone using the same app instance. Do not expose a deployment publicly unless access is restricted at the network or hosting layer.

## Application Pages

The top navigation contains three pages:

- **Company Search**: Search a ticker to fetch financial statements, recent news, stock price, and analyst ratings together. Use the result selector to navigate among the three views; stock price and analyst ratings is shown first by default, followed by financial statements and recent news. Successful results remain available when switching app pages during the session. A compact favourites row below the search bar shows AAPL, NVDA, and MU with prices cached for five minutes; clicking one fetches all three result views.
- **Company Comparison**: Compare two companies' prices and financial metrics.
- **Recently Viewed**: Review saved search records, shown five at a time with a Show more control. Select View to open a read-only result dialog. New single-company records retain all three fetched datasets; older records fetch stock price and analyst ratings when opened. Comparison records show matching data cached in the current app session, when available. Each row also shows its associated note count and provides a Notes action when notes are available.

Search history is temporarily stored in `.cache/nimbus/search_history.csv`. It includes search metadata and, for new single-company searches, all three serialized result datasets. Older records retain their originally saved result. The cache is local to the machine and is excluded from Git.

The floating Notes button is available while viewing an active company search or comparison. Notes are stored locally in `.cache/nimbus/notes.db`, can be reviewed globally, and are associated with the specific search record when possible. New notes remain drafts until the user submits **Save (Ctrl+Enter)**; blank drafts are not persisted. Because the demo has no authentication, local history and notes are shared by users of the same app instance.

## Project Structure

- `src/app.py`: Streamlit entry point, shared page styling, and navigation.
- `src/analysis.py`: Shared Yahoo Finance data-access functions.
- `src/features/company_search.py`: Company Search page and result rendering.
- `src/features/favourites.py`: Fixed favourite-company cards and cached price lookup.
- `src/features/company_comparison.py`: Company Comparison page, metrics, and Plotly chart.
- `src/features/history.py`: Local CSV search-history persistence and normalization.
- `src/features/recent_history.py`: Recently Viewed page, five-row expansion, result dialogs, and per-search note actions.
- `src/features/notes.py`: Fixed floating Notes control, note editor, global past-notes list, and local SQLite persistence.
- `assets/`: Nimbus logos and optional company logos.
- `scripts/nimbus-aws.yaml`: AWS CloudFormation deployment template.
- `filings.ipynb`, `news.ipynb`, `stock_price_ratings.ipynb`: Exploratory notebooks.
- `requirements.txt`: Python dependencies.

See [src/features/README.md](src/features/README.md) for feature-module ownership.

## Requirements and Local Setup

The app is tested with Python 3.14.7 and Streamlit 1.65.0. Use Python 3.10 or newer. Dependencies are listed in `requirements.txt`, including Streamlit, pandas, yfinance, and Plotly.

- Python 3.14 (recommended for this project environment)
- Streamlit
- pandas
- plotly
- yfinance
- git
- AWS account access for CloudFormation deployment (optional for local use)

From the project root:

```powershell
py -3.14 -m venv nimbus
.\nimbus\Scripts\python.exe -m pip install --upgrade pip
.\nimbus\Scripts\python.exe -m pip install -r requirements.txt
.\nimbus\Scripts\python.exe -m streamlit run src/app.py
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run src/app.py
```

Streamlit prints the local URL, usually `http://localhost:8501`. The environment folders and `.cache/` are ignored by Git.

## AWS Deployment

The CloudFormation template provisions an EC2-hosted Streamlit app in `us-east-1`, accessible on port `8501`. It requires an EC2 key pair and a Git repository URL. The template installs Python 3.11 to create the app's virtual environment. The `GitHubRepoUrl` parameter defaults to this repository; update it if deploying a fork.

To deploy, open CloudFormation in `us-east-1`, create a stack using `scripts/nimbus-aws.yaml`, provide the required parameters, and wait for the stack outputs. The `StreamlitUrl` output provides the app address. AWS deployment has not been validated against a live account in this development environment.

## Credits

Team Members: Wei Zihao, Paavas Bansal, Nicolyne Tiana Lie

Course: DS600 Cloud Computing for Economics, SMU MDSE
