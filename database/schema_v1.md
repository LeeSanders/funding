# Database Schema V1

## Design Goals

- Support 6-digit fund code as the first-class business key.
- Keep analysis explainable with technical, news, event and risk snapshots.
- Support user-isolated portfolios, daily valuation and OCR import workflow.
- Leave room for recommendation history, event linkage and production data refresh.

## Tables

### users
- Stores user identity and login base data.
- One user can own multiple portfolios and OCR jobs.

### funds
- Master data table keyed by `code`.
- Stores fund type, risk level, theme, benchmark and latest valuation cache.

### fund_tags / fund_tag_relations
- Support multi-tag classification such as theme, sector, style and strategy labels.

### news_events
- Stores normalized news or policy events.
- Deduplicated by `event_hash`.

### event_fund_links
- Connects events to funds with relation score and impact label.

### analysis_snapshots
- Stores explainable fund analysis snapshots.
- Includes decision, sub-scores, reasons, events and risks in JSON text form.

### recommendation_runs / recommendation_items
- Stores a recommendation batch and ranked recommendation items.
- Makes it possible to review recommendation history later.

### portfolios
- User portfolio container.
- Supports default portfolio and future multiple-account expansion.

### portfolio_holdings
- Stores the latest confirmed holdings per fund in a portfolio.
- Unique key on `portfolio_id + fund_code`.

### valuation_snapshots
- Stores valuation results for a portfolio-fund pair.
- Can be refreshed intraday by scheduled tasks.

### ocr_jobs / ocr_extraction_items
- Stores uploaded OCR jobs and parsed holding items.
- Supports confidence display, matching correction and confirmation flow.

## Key Indexes

- `ix_funds_theme`: filter by theme.
- `ix_news_events_theme_published_at`: list latest events by theme.
- `ix_analysis_snapshots_fund_code_created_at`: fetch latest analysis per fund.
- `ix_recommendation_runs_strategy_created_at`: fetch latest recommendation batch.
- `ix_portfolios_user_id`: isolate user portfolios.
- `ix_valuation_snapshots_portfolio_fund`: locate valuation rows fast.
- `ix_ocr_jobs_user_id_created_at`: query recent OCR history.

## Migration Files

- Alembic config: `backend/alembic.ini`
- Migration env: `backend/migrations/env.py`
- Initial migration: `backend/migrations/versions/20260506_0001_schema_v1.py`
- Plain SQL: `database/schema_v1.sql`
