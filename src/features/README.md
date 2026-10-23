# Feature Modules

Each user-facing page or feature is implemented in its own module:

- `company_search.py`: ticker search, data retrieval orchestration, retained results, and the favourites-row placement.
- `favourites.py`: fixed AAPL, NVDA, and MU buttons with latest prices cached for five minutes.
- `company_comparison.py`: two-company metrics and price-history comparison.
- `recent_history.py`: display of saved searches, five-row expansion, and read-only result dialogs.
- `history.py`: shared CSV persistence and normalization, including saved single-search results.

`src/app.py` owns shared app configuration, styling, and page navigation. Shared
Yahoo Finance data-access functions live in `src/analysis.py`. Local history is
stored under the project-level `.cache/nimbus/` directory and should not be committed.