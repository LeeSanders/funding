from collections import defaultdict
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import FundAnalysisSnapshot
from app.models.fund import Fund
from app.models.portfolio import PortfolioHolding, ValuationSnapshot
from app.schemas.dashboard import (
    DashboardFundItem,
    DashboardImpactItem,
    DashboardMessageItem,
    DashboardResponse,
    DashboardThemeItem,
)
from app.services.external_fund_service import _classify_fund_board, fetch_top_gainer_fund_candidates


DEFAULT_WATCHLIST_CODES = ["016370", "021933", "021735", "000011"]


def _dashboard_codes(db: Session, limit: int = 8) -> List[str]:
    codes: List[str] = []
    seen = set()

    recommendation_codes = [item.code for item in fetch_top_gainer_fund_candidates(limit=12)]
    cached_codes = db.scalars(select(Fund.code).order_by(Fund.latest_volume_rank.asc(), Fund.code.asc())).all()

    for code in [*recommendation_codes, *cached_codes, *DEFAULT_WATCHLIST_CODES]:
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
        if len(codes) >= limit:
            break
    return codes


def _build_focus_funds(analyses) -> List[DashboardFundItem]:
    focus_funds = []
    for item in analyses:
        focus_funds.append(
            DashboardFundItem(
                code=item.fund.code,
                name=item.fund.name,
                theme=_classify_fund_board(item.fund.name),
                decision=item.decision,
                score=item.score,
                technical_score=item.technical.score,
                news_score=item.news.score,
                risk_score=item.risk.score,
                estimated_change_rate=item.fund.estimated_change_rate,
                updated_at=item.updated_at,
            )
        )
    return sorted(focus_funds, key=lambda item: item.score, reverse=True)


def _latest_analysis_snapshot_map(db: Session) -> Dict[str, FundAnalysisSnapshot]:
    snapshots = db.scalars(select(FundAnalysisSnapshot).order_by(FundAnalysisSnapshot.id.desc())).all()
    latest: Dict[str, FundAnalysisSnapshot] = {}
    for item in snapshots:
        if item.fund_code not in latest:
            latest[item.fund_code] = item
    return latest


def _latest_valuation_map(db: Session) -> Dict[str, ValuationSnapshot]:
    snapshots = db.scalars(select(ValuationSnapshot).order_by(ValuationSnapshot.id.desc())).all()
    latest: Dict[str, ValuationSnapshot] = {}
    for item in snapshots:
        if item.fund_code not in latest:
            latest[item.fund_code] = item
    return latest


def _build_focus_funds_from_db(db: Session, codes: List[str]) -> List[DashboardFundItem]:
    snapshot_map = _latest_analysis_snapshot_map(db)
    funds = {item.code: item for item in db.scalars(select(Fund).where(Fund.code.in_(codes))).all()}
    items: List[DashboardFundItem] = []
    for code in codes:
        fund = funds.get(code)
        snapshot = snapshot_map.get(code)
        if not fund or not snapshot:
            continue
        items.append(
            DashboardFundItem(
                code=fund.code,
                name=fund.name,
                theme=_classify_fund_board(fund.name),
                decision=snapshot.decision,
                score=snapshot.score,
                technical_score=snapshot.technical_score,
                news_score=snapshot.news_score,
                risk_score=snapshot.risk_score,
                estimated_change_rate=fund.estimated_change_rate,
                updated_at=snapshot.updated_at,
            )
        )
    return sorted(items, key=lambda item: item.score, reverse=True)


def _build_theme_radar(focus_funds: List[DashboardFundItem]) -> List[DashboardThemeItem]:
    theme_buckets: Dict[str, List[float]] = defaultdict(list)
    for item in focus_funds:
        theme_buckets[item.theme].append(item.score)
    return sorted(
        [
            DashboardThemeItem(name=name, value=round(sum(values) / len(values), 2), count=len(values))
            for name, values in theme_buckets.items()
        ],
        key=lambda item: item.value,
        reverse=True,
    )


def _build_real_headlines(db: Session, focus_funds: List[DashboardFundItem]) -> List[DashboardMessageItem]:
    valuation_map = _latest_valuation_map(db)
    holdings = db.scalars(select(PortfolioHolding)).all()
    holding_codes = {item.fund_code for item in holdings}

    headlines: List[DashboardMessageItem] = []

    if holdings:
        holding_details = []
        total_daily_profit = 0.0
        updated_at = ""
        for holding in holdings:
            valuation = valuation_map.get(holding.fund_code)
            fund = db.get(Fund, holding.fund_code)
            est_nav = valuation.estimated_nav if valuation else (fund.estimated_nav if fund else 0.0)
            est_rate = valuation.estimated_change_rate if valuation else (fund.estimated_change_rate if fund else 0.0)
            method = valuation.valuation_method if valuation else "cached"
            item_updated_at = valuation.updated_at if valuation else ""
            previous_nav = est_nav / (1 + est_rate / 100.0) if est_nav and abs(est_rate) > 0.0001 else est_nav
            estimated_profit = holding.shares * (est_nav - previous_nav) if previous_nav else 0.0
            total_daily_profit += estimated_profit
            if item_updated_at and item_updated_at > updated_at:
                updated_at = item_updated_at
            holding_details.append(
                {
                    "code": holding.fund_code,
                    "name": fund.name if fund else holding.fund_code,
                    "estimated_profit": estimated_profit,
                    "valuation_method": method,
                }
            )
        updated_count = sum(1 for item in holding_details if item["valuation_method"] == "official_nav")
        best_holding = max(holding_details, key=lambda item: abs(item["estimated_profit"]))
        holding_summary = (
            f"{updated_count}/{len(holdings)} 只持仓已切到正式净值，"
            f"当前组合日收益 {total_daily_profit:+.2f} 元，"
            f"{best_holding['name']} 贡献 {best_holding['estimated_profit']:+.2f} 元。"
        )
        headlines.append(
            DashboardMessageItem(
                fund_code=best_holding["code"],
                fund_name=best_holding["name"],
                title="当前持仓与估值同步摘要",
                text=holding_summary,
                channel="持仓",
                source="持仓实时估值",
                published_at=updated_at,
                theme="组合持仓",
                impacts=[
                    DashboardImpactItem(
                        code=best_holding["code"],
                        name=best_holding["name"],
                        relation=f"日收益 {best_holding['estimated_profit']:+.2f} 元 | 估值口径 {best_holding['valuation_method']}",
                        theme=_classify_fund_board(best_holding["name"]),
                    )
                ],
            )
        )

    if focus_funds:
        top_analysis = focus_funds[0]
        headlines.append(
            DashboardMessageItem(
                fund_code=top_analysis.code,
                fund_name=top_analysis.name,
                title=f"{top_analysis.name} 是当前分析优先级最高的基金",
                text=(
                    f"综合 {top_analysis.score:.1f} 分，结论 {top_analysis.decision}，"
                    f"技术 {top_analysis.technical_score:.1f} / 消息 {top_analysis.news_score:.1f} / 风险 {top_analysis.risk_score:.1f}。"
                ),
                channel="分析",
                source="单基金分析",
                published_at=top_analysis.updated_at,
                theme=top_analysis.theme,
                impacts=[
                    DashboardImpactItem(
                        code=top_analysis.code,
                        name=top_analysis.name,
                        relation=f"当前结论：{top_analysis.decision}",
                        theme=top_analysis.theme,
                    )
                ],
            )
        )

    recommended_focus = focus_funds[0] if focus_funds else None
    if recommended_focus:
        headlines.append(
            DashboardMessageItem(
                fund_code=recommended_focus.code,
                fund_name=recommended_focus.name,
                title=f"{recommended_focus.name} 进入推荐观察池",
                text=(
                    f"所属方向 {recommended_focus.theme}，综合 {recommended_focus.score:.1f} 分，"
                    f"当前结论 {recommended_focus.decision}，盘中估值 {recommended_focus.estimated_change_rate:+.2f}%。"
                ),
                channel="推荐",
                source="基金推荐",
                published_at=recommended_focus.updated_at,
                theme=recommended_focus.theme,
                impacts=[
                    DashboardImpactItem(
                        code=recommended_focus.code,
                        name=recommended_focus.name,
                        relation=f"推荐观察 | {recommended_focus.decision}",
                        theme=recommended_focus.theme,
                    )
                ],
            )
        )

    ordered = [item for item in headlines if item.channel != "持仓"]
    holding_item = next((item for item in headlines if item.channel == "持仓"), None)
    if holding_item:
        ordered.append(holding_item)
    return ordered[:3]


def get_dashboard(db: Session) -> DashboardResponse:
    focus_funds = _build_focus_funds_from_db(db, _dashboard_codes(db))
    themes = _build_theme_radar(focus_funds)
    headlines = _build_real_headlines(db, focus_funds)
    timeline = headlines[:]

    avg_news_score = round(sum(item.news_score for item in focus_funds) / max(len(focus_funds), 1), 2)
    avg_change_rate = round(sum(item.estimated_change_rate for item in focus_funds) / max(len(focus_funds), 1), 2)
    market_heat_delta = (
        f"监控池均值 {avg_change_rate:+.2f}% ，实时消息面均分 {avg_news_score:.1f}"
        if focus_funds
        else "当前监控池为空，请先查询基金或录入持仓。"
    )

    return DashboardResponse(
        market_heat=avg_news_score,
        market_heat_delta=market_heat_delta,
        event_count=len(timeline),
        pool_count=len(focus_funds),
        focus_funds=focus_funds[:3],
        themes=themes[:4],
        headlines=headlines,
        timeline=timeline[:10],
    )
