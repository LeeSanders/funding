CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(128) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(64) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE funds (
  code VARCHAR(6) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  fund_type VARCHAR(64) NOT NULL,
  risk_level VARCHAR(32) NOT NULL,
  theme VARCHAR(64) NOT NULL,
  company VARCHAR(64),
  benchmark VARCHAR(128),
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  latest_nav NUMERIC(12, 4) NOT NULL DEFAULT 0,
  estimated_nav NUMERIC(12, 4) NOT NULL DEFAULT 0,
  estimated_change_rate NUMERIC(8, 4) NOT NULL DEFAULT 0,
  latest_volume_rank INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE fund_tags (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  tag_type VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_fund_tags_name_type UNIQUE (name, tag_type)
);

CREATE TABLE fund_tag_relations (
  id BIGSERIAL PRIMARY KEY,
  fund_code VARCHAR(6) NOT NULL REFERENCES funds(code) ON DELETE CASCADE,
  tag_id BIGINT NOT NULL REFERENCES fund_tags(id) ON DELETE CASCADE,
  weight NUMERIC(8, 4) NOT NULL DEFAULT 1,
  CONSTRAINT uq_fund_tag_relations_code_tag UNIQUE (fund_code, tag_id)
);

CREATE TABLE news_events (
  id BIGSERIAL PRIMARY KEY,
  source VARCHAR(64) NOT NULL,
  title VARCHAR(255) NOT NULL,
  content TEXT,
  theme VARCHAR(64) NOT NULL,
  sentiment VARCHAR(16) NOT NULL,
  strength VARCHAR(16) NOT NULL,
  published_at TIMESTAMPTZ NOT NULL,
  event_hash VARCHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE event_fund_links (
  id BIGSERIAL PRIMARY KEY,
  event_id BIGINT NOT NULL REFERENCES news_events(id) ON DELETE CASCADE,
  fund_code VARCHAR(6) NOT NULL REFERENCES funds(code) ON DELETE CASCADE,
  relation_score NUMERIC(8, 4) NOT NULL DEFAULT 0,
  impact_label VARCHAR(64) NOT NULL,
  CONSTRAINT uq_event_fund_links_event_fund UNIQUE (event_id, fund_code)
);

CREATE TABLE analysis_snapshots (
  id BIGSERIAL PRIMARY KEY,
  fund_code VARCHAR(6) NOT NULL REFERENCES funds(code) ON DELETE CASCADE,
  decision VARCHAR(32) NOT NULL,
  confidence VARCHAR(16) NOT NULL,
  action VARCHAR(32) NOT NULL,
  holding_window VARCHAR(32) NOT NULL,
  score NUMERIC(8, 2) NOT NULL,
  technical_score NUMERIC(8, 2) NOT NULL,
  news_score NUMERIC(8, 2) NOT NULL,
  risk_score NUMERIC(8, 2) NOT NULL,
  summary_title VARCHAR(255) NOT NULL,
  summary_text TEXT NOT NULL,
  reasons_json TEXT NOT NULL,
  events_json TEXT NOT NULL,
  risks_json TEXT NOT NULL,
  data_version VARCHAR(32) NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE recommendation_runs (
  id BIGSERIAL PRIMARY KEY,
  strategy VARCHAR(32) NOT NULL,
  title VARCHAR(128) NOT NULL,
  description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE recommendation_items (
  id BIGSERIAL PRIMARY KEY,
  run_id BIGINT NOT NULL REFERENCES recommendation_runs(id) ON DELETE CASCADE,
  fund_code VARCHAR(6) NOT NULL REFERENCES funds(code) ON DELETE CASCADE,
  rank INTEGER NOT NULL,
  decision VARCHAR(32) NOT NULL,
  score NUMERIC(8, 2) NOT NULL,
  reason TEXT NOT NULL,
  risk TEXT NOT NULL,
  CONSTRAINT uq_recommendation_items_run_fund UNIQUE (run_id, fund_code)
);

CREATE TABLE portfolios (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(64) NOT NULL,
  risk_profile VARCHAR(16) NOT NULL DEFAULT 'balanced',
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE portfolio_holdings (
  id BIGSERIAL PRIMARY KEY,
  portfolio_id BIGINT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  fund_code VARCHAR(6) NOT NULL REFERENCES funds(code) ON DELETE RESTRICT,
  shares NUMERIC(18, 4) NOT NULL,
  cost_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
  source VARCHAR(16) NOT NULL DEFAULT 'manual',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_portfolio_holdings_portfolio_fund UNIQUE (portfolio_id, fund_code)
);

CREATE TABLE valuation_snapshots (
  id BIGSERIAL PRIMARY KEY,
  portfolio_id BIGINT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  fund_code VARCHAR(6) NOT NULL REFERENCES funds(code) ON DELETE CASCADE,
  estimated_nav NUMERIC(12, 4) NOT NULL,
  estimated_change_rate NUMERIC(8, 4) NOT NULL,
  estimated_profit NUMERIC(18, 2) NOT NULL DEFAULT 0,
  market_value NUMERIC(18, 2) NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE ocr_jobs (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  portfolio_id BIGINT REFERENCES portfolios(id) ON DELETE SET NULL,
  filename VARCHAR(255) NOT NULL,
  storage_key VARCHAR(255),
  status VARCHAR(16) NOT NULL DEFAULT 'pending',
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

CREATE TABLE ocr_extraction_items (
  id BIGSERIAL PRIMARY KEY,
  job_id BIGINT NOT NULL REFERENCES ocr_jobs(id) ON DELETE CASCADE,
  fund_code VARCHAR(6) NOT NULL,
  fund_name VARCHAR(128) NOT NULL,
  shares NUMERIC(18, 4) NOT NULL,
  amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
  confidence VARCHAR(16) NOT NULL,
  matched_fund_code VARCHAR(6) REFERENCES funds(code) ON DELETE SET NULL,
  confirmed BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_funds_theme ON funds(theme);
CREATE INDEX ix_news_events_theme_published_at ON news_events(theme, published_at);
CREATE INDEX ix_analysis_snapshots_fund_code_created_at ON analysis_snapshots(fund_code, created_at DESC);
CREATE INDEX ix_recommendation_runs_strategy_created_at ON recommendation_runs(strategy, created_at DESC);
CREATE INDEX ix_portfolios_user_id ON portfolios(user_id);
CREATE INDEX ix_valuation_snapshots_portfolio_fund ON valuation_snapshots(portfolio_id, fund_code);
CREATE INDEX ix_ocr_jobs_user_id_created_at ON ocr_jobs(user_id, created_at DESC);
