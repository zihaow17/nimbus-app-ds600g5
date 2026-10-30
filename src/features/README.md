# Feature Modules

Each user-facing page or feature is implemented in its own module:

- `company_search.py`: ticker search, data retrieval orchestration, retained results, and the favourites-row placement.
- `favourites.py`: fixed AAPL, NVDA, and MU buttons with latest prices cached for five minutes.
- `company_comparison.py`: two-company metrics and price-history comparison.
- `recent_history.py`: display of saved searches, five-row expansion, read-only result dialogs, and per-search note counts/actions.
- `history.py`: shared CSV persistence and normalization, including stable history IDs and saved single-search results.
- `notes.py`: fixed floating Notes control, non-blocking editor, global past-notes list, explicit draft saving, and local SQLite persistence.

`src/app.py` owns shared app configuration, styling, and page navigation. Shared
Yahoo Finance data-access functions live in `src/analysis.py`. Local history and
notes are stored under the project-level `.cache/nimbus/` directory and should not
be committed. Notes are linked to individual search history IDs when available;
older notes can be matched by their company or comparison context.