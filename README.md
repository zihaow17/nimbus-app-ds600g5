# Nimbus Financial Data Explorer

A small Streamlit app for looking up financial information by stock ticker. Data
is retrieved from Yahoo Finance through `yfinance` and may be unavailable,
delayed, or incomplete.

## Features

- Financial statements: income statement, balance sheet, and cash flow data.
- Recent news: up to five articles, with titles and short descriptions.
- Stock price and analyst recommendations: current reported price and up to ten recent recommendation rows.

The app currently labels the financial-statement view as “filings,” but it does
not retrieve SEC filing documents.

## Project layout

- `src/app.py`: Streamlit app entry point.
- `src/analysis.py`: Shared Yahoo Finance data functions.
- `src/features/`: Future one-file-per-feature modules; see its README.
- `filings.ipynb`, `news.ipynb`, `stock_price_ratings.ipynb`: Exploratory notebooks.

As the app grows, add each feature as a separate Python module under
`src/features/`. The notebooks are exploratory examples; the app uses the
functions in `src/analysis.py`.

## Installation

From the project root, create and activate the `ds600p` virtual environment, then
install the dependencies:

```bash
python3 -m venv ds600p
source ds600p/bin/activate
python -m pip install -r requirements.txt
```

## Run the app

With the virtual environment activated, start Streamlit from the project root:

```bash
streamlit run src/app.py
```

Streamlit prints a local URL to open in your browser. Enter a ticker symbol and
choose an analysis type to load its available data.

## Dependencies

Dependencies are listed in `requirements.txt`: Streamlit, pandas, and yfinance.