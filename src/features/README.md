# Feature Modules

Each user-facing page or feature is implemented in its own module:

- `company_search.py`: ticker search, data retrieval orchestration, retained results, and the favourites-row placement.
- `favourites.py`: fixed AAPL, NVDA, and MU buttons with latest prices cached for five minutes.
- `company_comparison.py`: two-company metrics and price-history comparison.
- `recent_history.py`: display of saved searches, five-row expansion, and read-only result dialogs.
- `history.py`: user-scoped PostgreSQL persistence and normalization, including saved single-search results.
- `notes.py`: context-aware note drafts and explicitly saved user/search-scoped PostgreSQL notes.

`src/app.py` owns shared app configuration, styling, and page navigation. Shared
Yahoo Finance data-access functions live in `src/analysis.py`. PostgreSQL connection
configuration and schema setup live in `src/database.py`.

The runtime flow is `src/app.py` -> the selected feature module -> shared data
access and persistence modules. Search/comparison actions fetch external company
data and write user-scoped history; the Recently Viewed and Notes features read
that PostgreSQL data. Notes drafts stay in Streamlit session state until saved.