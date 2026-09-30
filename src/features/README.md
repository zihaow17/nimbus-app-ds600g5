# Feature modules

Add each user-facing feature as its own Python module in this directory, such as
`filings.py`, `news.py`, or `stock_price_ratings.py`.

Keep the Streamlit entry point in `src/app.py`. Shared data-access helpers remain
in `src/analysis.py` until they are intentionally reorganized.