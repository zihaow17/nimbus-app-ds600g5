# Feature Modules

Each user-facing page or feature is implemented in its own module:

- `company_search.py`: ticker search, data retrieval orchestration, and retained results.
- `company_comparison.py`: two-company metrics and price-history comparison.
- `favourites.py`: placeholder for the future favourites feature.
- `recent_history.py`: display of saved searches and five-row expansion.
- `history.py`: shared CSV persistence and normalization used by search and comparison.

`src/app.py` owns shared app configuration, styling, and page navigation. Shared
Yahoo Finance data-access functions live in `src/analysis.py`. Local history is
stored under the project-level `.cache/nimbus/` directory and should not be committed.