from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import akshare as ak
import json
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.portfolio import PortfolioHolding, ValuationSnapshot
from app.schemas.portfolio import (
    HoldingAdjustRequest,
    HoldingCreate,
    HoldingItem,
    HoldingUpdateRequest,
    PortfolioResponse,
    PortfolioSummaryResponse,
)
from app.services.external_fund_service import fetch_fund_profile
from urllib.request import Request, urlopen
import json


REFRESH_INTERVAL_MINUTES = 10
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
TENCENT_USER_AGENT = "Mozilla/5.0"
DEBUG_ENV_PATH = Path(".dbg/valuation-mismatch.env")


# #region debug-point A:valuation-report
def _debug_report(hypothesis_id: str, location: str, msg: str, data: Optional[Dict[str, object]] = None) -> None:
    _url = "http://127.0.0.1:7778/event"
    _session = "valuation-mismatch"
    try:
        if DEBUG_ENV_PATH.exists():
            _content = DEBUG_ENV_PATH.read_text(encoding="utf-8")
            for _line in _content.splitlines():
                if _line.startswith("DEBUG_SERVER_URL="):
                    _url = _line.split("=", 1)[1].strip() or _url
                elif _line.startswith("DEBUG_SESSION_ID="):
                    _session = _line.split("=", 1)[1].strip() or _session
        payload = {
            "sessionId": _session,
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "msg": f"[DEBUG] {msg}",
            "data": data or {},
            "ts": int(datetime.now().timestamp() * 1000),
        }
        urlopen(
            Request(
                _url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            ),
            timeout=1,
        ).read()
    except Exception:
        pass
# #endregion


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def _is_stale(updated_at: str) -> bool:
    dt = _parse_dt(updated_at)
    if not dt:
        return True
    return datetime.now() - dt >= timedelta(minutes=REFRESH_INTERVAL_MINUTES)


def _format_stock_symbol(code: str) -> str:
    if code.startswith(("6", "9")):
        return f"sh{code}"
    return f"sz{code}"


def _fetch_tencent_quote(symbols: List[str]) -> Dict[str, float]:
    if not symbols:
        return {}
    request = Request(
        TENCENT_QUOTE_URL + ",".join(symbols),
        headers={"User-Agent": TENCENT_USER_AGENT, "Referer": "https://gu.qq.com/"},
    )
    with urlopen(request, timeout=15) as response:
        payload = response.read().decode("gbk", errors="ignore")

    result: Dict[str, float] = {}
    for line in payload.split(";"):
        if not line.strip():
            continue
        parts = line.split("~")
        if len(parts) < 33:
            continue
        code = parts[2].strip()
        change_rate = 0.0
        try:
            change_rate = float(parts[32])
        except (TypeError, ValueError):
            pass
        if code:
            result[code] = change_rate
    return result


@lru_cache(maxsize=256)
def _get_fund_holdings_proxy(code: str, year: str) -> List[Dict[str, float]]:
    df = ak.fund_portfolio_hold_em(symbol=code, date=year)
    if df.empty:
        return []
    latest_quarter = str(df["季度"].iloc[0])
    latest_df = df[df["季度"] == latest_quarter].copy()
    latest_df = latest_df.head(10)
    holdings: List[Dict[str, float]] = []
    for _, row in latest_df.iterrows():
        try:
            weight = float(row["占净值比例"])
        except (TypeError, ValueError):
            weight = 0.0
        stock_code = str(row["股票代码"]).zfill(6)
        if not stock_code or weight <= 0:
            continue
        holdings.append({"stock_code": stock_code, "weight": weight})
    return holdings


def _estimate_rate_from_holdings(code: str) -> Optional[float]:
    current_year = str(datetime.now().year)
    previous_year = str(datetime.now().year - 1)
    holdings = _get_fund_holdings_proxy(code, current_year) or _get_fund_holdings_proxy(code, previous_year)
    if not holdings:
        return None
    quotes = _fetch_tencent_quote([_format_stock_symbol(item["stock_code"]) for item in holdings])
    weighted_sum = 0.0
    total_weight = 0.0
    for item in holdings:
        stock_code = item["stock_code"]
        if stock_code not in quotes:
            continue
        weight = float(item["weight"])
        weighted_sum += quotes[stock_code] * weight
        total_weight += weight
    if total_weight <= 0:
        return None
    # 以披露仓位作为权重上限，未披露部分按 0 处理，避免放大估值波动
    return round(weighted_sum / 100.0, 4)


def _pick_valuation_method(direct_rate: float, proxy_rate: Optional[float]) -> tuple[float, str]:
    if abs(direct_rate) > 0.001:
        return direct_rate, "eastmoney_realtime"
    if proxy_rate is not None:
        return proxy_rate, "holding_proxy"
    return direct_rate, "latest_nav_fallback"


def _is_official_nav_ready(payload) -> bool:
    latest_nav_date = str(payload.metrics.get("latest_nav_date") or "").strip()
    if latest_nav_date != _today_str():
        return False
    return payload.latest_nav > 0


def _upsert_holding(db: Session, fund_code: str, delta_shares: float, delta_cost_amount: float, source: str) -> None:
    existing = db.scalar(select(PortfolioHolding).where(PortfolioHolding.fund_code == fund_code))
    if existing:
        existing.shares = round(existing.shares + delta_shares, 2)
        existing.cost_amount = round(existing.cost_amount + delta_cost_amount, 2)
        existing.source = source or existing.source
        if existing.shares <= 0:
            db.delete(existing)
    elif delta_shares > 0:
        db.add(
            PortfolioHolding(
                fund_code=fund_code,
                shares=round(delta_shares, 2),
                cost_amount=round(delta_cost_amount, 2),
                source=source,
            )
        )


def _refresh_realtime_valuation(db: Session, fund_code: str) -> Fund:
    payload = fetch_fund_profile(fund_code)
    fund = db.get(Fund, fund_code)
    if not fund:
        fund = Fund(code=payload.code)
        db.add(fund)

    fund.name = payload.name
    fund.fund_type = payload.fund_type
    fund.risk_level = payload.risk_level
    fund.theme = payload.theme
    fund.company = payload.company
    fund.latest_nav = payload.latest_nav or 0.0
    if _is_official_nav_ready(payload):
        estimated_change_rate = float(payload.metrics.get("official_daily_rate") or 0.0)
        method = "official_nav"
        estimated_nav = payload.latest_nav or 0.0
        direct_rate = payload.estimated_change_rate or 0.0
        proxy_rate = None
    else:
        direct_rate = payload.estimated_change_rate or 0.0
        proxy_rate = _estimate_rate_from_holdings(fund_code)
        estimated_change_rate, method = _pick_valuation_method(direct_rate, proxy_rate)
        estimated_nav = (fund.latest_nav or 0.0) * (1 + estimated_change_rate / 100.0) if fund.latest_nav else 0.0
    # #region debug-point A:refresh-valuation
    _debug_report(
        "A",
        "portfolio_service:_refresh_realtime_valuation",
        "valuation refreshed",
        {
            "fund_code": fund_code,
            "latest_nav": fund.latest_nav,
            "payload_estimated_nav": payload.estimated_nav,
            "payload_direct_rate": direct_rate,
            "proxy_rate": proxy_rate,
            "selected_rate": estimated_change_rate,
            "selected_method": method,
            "computed_estimated_nav": estimated_nav,
        },
    )
    # #endregion
    fund.estimated_nav = estimated_nav or payload.estimated_nav or payload.latest_nav or 0.0
    fund.estimated_change_rate = estimated_change_rate

    valuation = db.scalar(
        select(ValuationSnapshot)
        .where(ValuationSnapshot.fund_code == fund_code)
        .order_by(ValuationSnapshot.id.desc())
        .limit(1)
    )
    if valuation:
        valuation.estimated_nav = fund.estimated_nav
        valuation.estimated_change_rate = fund.estimated_change_rate
        valuation.valuation_method = method
        valuation.updated_at = _now_str()
    else:
        db.add(
            ValuationSnapshot(
                fund_code=fund_code,
                estimated_nav=fund.estimated_nav,
                estimated_change_rate=fund.estimated_change_rate,
                valuation_method=method,
                updated_at=_now_str(),
            )
        )
    setattr(fund, "_valuation_method", method)
    db.commit()
    db.refresh(fund)
    return fund


def _latest_valuation_map(db: Session) -> Dict[str, ValuationSnapshot]:
    valuations = db.scalars(select(ValuationSnapshot).order_by(ValuationSnapshot.id.desc())).all()
    latest: Dict[str, ValuationSnapshot] = {}
    for item in valuations:
        if item.fund_code not in latest:
            latest[item.fund_code] = item
    return latest


def get_portfolio(db: Session, refresh: bool = False) -> PortfolioResponse:
    holdings = db.scalars(select(PortfolioHolding)).all()
    # #region debug-point B:portfolio-start
    _debug_report("B", "portfolio_service:get_portfolio:start", "portfolio requested", {"refresh": refresh, "holding_count": len(holdings), "holding_codes": [item.fund_code for item in holdings]})
    # #endregion
    valuation_map_before = _latest_valuation_map(db)
    for holding in holdings:
        try:
            valuation = valuation_map_before.get(holding.fund_code)
            if refresh or not valuation or _is_stale(valuation.updated_at):
                _refresh_realtime_valuation(db, holding.fund_code)
        except ValueError:
            continue

    fund_map = {fund.code: fund for fund in db.scalars(select(Fund)).all()}
    valuation_map = _latest_valuation_map(db)

    holding_items: List[HoldingItem] = []
    market_value = 0.0
    daily_profit = 0.0
    updated_at = ""

    for holding in holdings:
        fund = fund_map[holding.fund_code]
        valuation = valuation_map.get(holding.fund_code)
        est_nav = valuation.estimated_nav if valuation else fund.estimated_nav
        est_rate = valuation.estimated_change_rate if valuation else fund.estimated_change_rate
        previous_nav = est_nav / (1 + est_rate / 100.0) if est_nav and abs(est_rate) > 0.0001 else (fund.latest_nav or est_nav or 0.0)
        est_profit = holding.shares * (est_nav - previous_nav) if previous_nav else 0.0
        # #region debug-point C:holding-valuation
        _debug_report(
            "C",
            "portfolio_service:get_portfolio:holding",
            "holding valuation calculated",
            {
                "fund_code": holding.fund_code,
                "shares": holding.shares,
                "cost_amount": holding.cost_amount,
                "latest_nav": fund.latest_nav,
                "estimated_nav": est_nav,
                "estimated_change_rate": est_rate,
                "reference_nav": previous_nav,
                "estimated_profit": round(est_profit, 4),
                "valuation_method": (getattr(valuation, "valuation_method", "") or getattr(fund, "_valuation_method", "cached")),
            },
        )
        # #endregion

        market_value += holding.shares * est_nav
        daily_profit += est_profit
        updated_at = max(updated_at, valuation.updated_at if valuation else "") if updated_at else (valuation.updated_at if valuation else "")
        holding_items.append(
            HoldingItem(
                id=holding.id,
                fund_code=holding.fund_code,
                fund_name=fund.name,
                shares=holding.shares,
                cost_amount=holding.cost_amount,
                estimated_nav=round(est_nav, 4),
                estimated_change_rate=est_rate,
                estimated_profit=round(est_profit, 2),
                valuation_method=(getattr(valuation, "valuation_method", "") or getattr(fund, "_valuation_method", "cached")),
                updated_at=valuation.updated_at if valuation else "",
            )
        )

    profit_rate = round((daily_profit / market_value) * 100, 2) if market_value else 0.0
    summary = PortfolioSummaryResponse(
        market_value=round(market_value, 2),
        daily_profit=round(daily_profit, 2),
        daily_profit_rate=profit_rate,
        holding_count=len(holding_items),
        updated_at=updated_at,
    )
    # #region debug-point D:portfolio-summary
    _debug_report("D", "portfolio_service:get_portfolio:summary", "portfolio summary built", {"market_value": round(market_value, 2), "daily_profit": round(daily_profit, 2), "daily_profit_rate": profit_rate, "updated_at": updated_at})
    # #endregion
    return PortfolioResponse(summary=summary, holdings=holding_items)


def create_holding(db: Session, payload: HoldingCreate) -> PortfolioResponse:
    _refresh_realtime_valuation(db, payload.fund_code)
    _upsert_holding(db, payload.fund_code, payload.shares, payload.cost_amount, payload.source)
    db.commit()
    return get_portfolio(db, refresh=True)


def adjust_holding(db: Session, holding_id: int, payload: HoldingAdjustRequest) -> PortfolioResponse:
    holding = db.get(PortfolioHolding, holding_id)
    if not holding:
        raise ValueError(f"持仓记录 {holding_id} 不存在")
    _upsert_holding(db, holding.fund_code, payload.delta_shares, payload.delta_cost_amount, holding.source)
    db.commit()
    return get_portfolio(db, refresh=False)


def update_holding(db: Session, holding_id: int, payload: HoldingUpdateRequest) -> PortfolioResponse:
    holding = db.get(PortfolioHolding, holding_id)
    if not holding:
        raise ValueError(f"持仓记录 {holding_id} 不存在")
    if payload.fund_code and payload.fund_code != holding.fund_code:
        _refresh_realtime_valuation(db, payload.fund_code)
        holding.fund_code = payload.fund_code
    if payload.shares is not None:
        holding.shares = round(payload.shares, 2)
    if payload.cost_amount is not None:
        holding.cost_amount = round(payload.cost_amount, 2)
    if holding.shares <= 0:
        db.delete(holding)
    db.commit()
    return get_portfolio(db, refresh=False)


def delete_holding(db: Session, holding_id: int) -> PortfolioResponse:
    holding = db.get(PortfolioHolding, holding_id)
    if not holding:
        raise ValueError(f"持仓记录 {holding_id} 不存在")
    db.delete(holding)
    db.commit()
    return get_portfolio(db, refresh=False)
