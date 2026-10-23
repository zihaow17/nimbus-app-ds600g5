# Feature Modules

Each user-facing page or feature is implemented in its own module:

- `company_search.py`: ticker search, data retrieval orchestration, and retained results.
- `favourites.py`: fixed AAPL, NVDA, and MU cards with briefly cached latest prices.
- `company_comparison.py`: two-company metrics and price-history comparison.
- `recent_history.py`: display of saved searches, five-row expansion, and read-only result dialog.
- `history.py`: shared CSV persistence and normalization, including saved single-search results.

`src/app.py` owns shared app configuration, styling, and page navigation. Shared
Yahoo Finance data-access functions live in `src/analysis.py`. Local history is
stored under the project-level `.cache/nimbus/` directory and should not be committed.