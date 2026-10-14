# Nimbus Financial Intelligence

## Overview

Nimbus is a Streamlit dashboard for exploring public company financial data. It retrieves market, statement, news, and analyst information from Yahoo Finance through `yfinance`. Local use still requires an internet connection for those data requests.

The app can run locally or be deployed to AWS with the CloudFormation template in `scripts/nimbus-aws.yaml`.

## Application Pages

The top navigation contains four pages:

- **Company Search**: Search a ticker for financial statements, recent news, or stock price and analyst ratings. Successful results remain available when switching pages during the session.
- **Company Comparison**: Compare two companies' prices and financial metrics.
- **Favourites**: Placeholder page; saving and managing favourites is not implemented yet.
- **Recently Viewed**: Review saved search records, shown five at a time with a Show more control.

Search history is temporarily stored in `.cache/nimbus/search_history.csv`. It contains search metadata such as tickers, company names, and timestamps, not downloaded financial datasets. The cache is local to the machine and is excluded from Git.

## Project Structure

- `src/app.py`: Streamlit entry point, shared page styling, and navigation.
- `src/analysis.py`: Shared Yahoo Finance data-access functions.
- `src/features/company_search.py`: Company Search page and result rendering.
- `src/features/company_comparison.py`: Company Comparison page, metrics, and Plotly chart.
- `src/features/favourites.py`: Favourites placeholder page.
- `src/features/history.py`: Local CSV search-history persistence and normalization.
- `src/features/recent_history.py`: Recently Viewed page and five-row expansion.
- `assets/`: Nimbus logos and optional company logos.
- `scripts/nimbus-aws.yaml`: AWS CloudFormation deployment template.
- `filings.ipynb`, `news.ipynb`, `stock_price_ratings.ipynb`: Exploratory notebooks.
- `requirements.txt`: Python dependencies.

See [src/features/README.md](src/features/README.md) for feature-module ownership.

## Requirements and Local Setup

The app is tested with Python 3.14.7 and Streamlit 1.65.0. Use Python 3.10 or newer; the app uses modern Python type syntax. Dependencies are listed in `requirements.txt`, including Streamlit, pandas, yfinance, and Plotly.

### Windows PowerShell

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

The CloudFormation template provisions an EC2-hosted Streamlit app in `us-east-1`, accessible on port `8501`. It requires an EC2 key pair and a Git repository URL. The template's default GitHub URL is a placeholder (`your-org/nimbus-app-ds600g5`); set it to the actual repository before creating a stack.

To deploy, open CloudFormation in `us-east-1`, create a stack using `scripts/nimbus-aws.yaml`, provide the required parameters, and wait for the stack outputs. The `StreamlitUrl` output provides the app address. AWS deployment has not been validated against a live account in this development environment.

## Credits

Team Members: Wei Zihao, Paavas Bansal, Nicolyne Tiana Lie

Course: DS600 Cloud Computing for Economics, SMU MDSE
