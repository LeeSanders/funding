"""schema v1

Revision ID: 20260506_0001
Revises:
Create Date: 2026-05-06 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "funds",
        sa.Column("code", sa.String(length=6), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("fund_type", sa.String(length=64), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("theme", sa.String(length=64), nullable=False),
        sa.Column("company", sa.String(length=64), nullable=True),
        sa.Column("benchmark", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("latest_nav", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("estimated_nav", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("estimated_change_rate", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("latest_volume_rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "fund_tags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("tag_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", "tag_type", name="uq_fund_tags_name_type"),
    )
    op.create_table(
        "fund_tag_relations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("fund_code", sa.String(length=6), sa.ForeignKey("funds.code", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), sa.ForeignKey("fund_tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weight", sa.Numeric(8, 4), nullable=False, server_default="1"),
        sa.UniqueConstraint("fund_code", "tag_id", name="uq_fund_tag_relations_code_tag"),
    )
    op.create_table(
        "news_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("theme", sa.String(length=64), nullable=False),
        sa.Column("sentiment", sa.String(length=16), nullable=False),
        sa.Column("strength", sa.String(length=16), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_hash", name="uq_news_events_hash"),
    )
    op.create_table(
        "event_fund_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("news_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fund_code", sa.String(length=6), sa.ForeignKey("funds.code", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_score", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("impact_label", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("event_id", "fund_code", name="uq_event_fund_links_event_fund"),
    )
    op.create_table(
        "analysis_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("fund_code", sa.String(length=6), sa.ForeignKey("funds.code", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("holding_window", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Numeric(8, 2), nullable=False),
        sa.Column("technical_score", sa.Numeric(8, 2), nullable=False),
        sa.Column("news_score", sa.Numeric(8, 2), nullable=False),
        sa.Column("risk_score", sa.Numeric(8, 2), nullable=False),
        sa.Column("summary_title", sa.String(length=255), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("reasons_json", sa.Text(), nullable=False),
        sa.Column("events_json", sa.Text(), nullable=False),
        sa.Column("risks_json", sa.Text(), nullable=False),
        sa.Column("data_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "recommendation_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "recommendation_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("recommendation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fund_code", sa.String(length=6), sa.ForeignKey("funds.code", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Numeric(8, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("risk", sa.Text(), nullable=False),
        sa.UniqueConstraint("run_id", "fund_code", name="uq_recommendation_items_run_fund"),
    )
    op.create_table(
        "portfolios",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("risk_profile", sa.String(length=16), nullable=False, server_default="balanced"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "portfolio_holdings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("portfolio_id", sa.BigInteger(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fund_code", sa.String(length=6), sa.ForeignKey("funds.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("shares", sa.Numeric(18, 4), nullable=False),
        sa.Column("cost_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "fund_code", name="uq_portfolio_holdings_portfolio_fund"),
    )
    op.create_table(
        "valuation_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("portfolio_id", sa.BigInteger(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fund_code", sa.String(length=6), sa.ForeignKey("funds.code", ondelete="CASCADE"), nullable=False),
        sa.Column("estimated_nav", sa.Numeric(12, 4), nullable=False),
        sa.Column("estimated_change_rate", sa.Numeric(8, 4), nullable=False),
        sa.Column("estimated_profit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("market_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "ocr_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("portfolio_id", sa.BigInteger(), sa.ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "ocr_extraction_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.BigInteger(), sa.ForeignKey("ocr_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fund_code", sa.String(length=6), nullable=False),
        sa.Column("fund_name", sa.String(length=128), nullable=False),
        sa.Column("shares", sa.Numeric(18, 4), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("matched_fund_code", sa.String(length=6), sa.ForeignKey("funds.code", ondelete="SET NULL"), nullable=True),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_funds_theme", "funds", ["theme"])
    op.create_index("ix_news_events_theme_published_at", "news_events", ["theme", "published_at"])
    op.create_index("ix_analysis_snapshots_fund_code_created_at", "analysis_snapshots", ["fund_code", "created_at"])
    op.create_index("ix_recommendation_runs_strategy_created_at", "recommendation_runs", ["strategy", "created_at"])
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"])
    op.create_index("ix_valuation_snapshots_portfolio_fund", "valuation_snapshots", ["portfolio_id", "fund_code"])
    op.create_index("ix_ocr_jobs_user_id_created_at", "ocr_jobs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ocr_jobs_user_id_created_at", table_name="ocr_jobs")
    op.drop_index("ix_valuation_snapshots_portfolio_fund", table_name="valuation_snapshots")
    op.drop_index("ix_portfolios_user_id", table_name="portfolios")
    op.drop_index("ix_recommendation_runs_strategy_created_at", table_name="recommendation_runs")
    op.drop_index("ix_analysis_snapshots_fund_code_created_at", table_name="analysis_snapshots")
    op.drop_index("ix_news_events_theme_published_at", table_name="news_events")
    op.drop_index("ix_funds_theme", table_name="funds")
    op.drop_table("ocr_extraction_items")
    op.drop_table("ocr_jobs")
    op.drop_table("valuation_snapshots")
    op.drop_table("portfolio_holdings")
    op.drop_table("portfolios")
    op.drop_table("recommendation_items")
    op.drop_table("recommendation_runs")
    op.drop_table("analysis_snapshots")
    op.drop_table("event_fund_links")
    op.drop_table("news_events")
    op.drop_table("fund_tag_relations")
    op.drop_table("fund_tags")
    op.drop_table("funds")
    op.drop_table("users")
