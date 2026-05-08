import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import FundAnalysisSnapshot
from app.models.fund import Fund
from app.models.portfolio import PortfolioHolding
from app.schemas.analysis import (
    AnalysisItem,
    FundAnalysisResponse,
    ScoreSummary,
    TrendChartEvent,
    TrendChartPayload,
    TrendChartPoint,
)
from app.schemas.fund import FundDetail
from app.services.ai_summary_service import generate_ai_summary
from app.services.external_fund_service import ExternalFundPayload, fetch_fund_profile
from app.services.message_service import build_event_cards, build_message_reason_text, fetch_message_snapshot


TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
TENCENT_USER_AGENT = "Mozilla/5.0"
SNAPSHOT_KEYS = {
    "fund_code",
    "decision",
    "confidence",
    "action",
    "holding_window",
    "score",
    "technical_score",
    "news_score",
    "risk_score",
    "summary_title",
    "summary_text",
    "reasons_json",
    "events_json",
    "risks_json",
    "updated_at",
}


def get_fund_or_404(db: Session, code: str) -> Fund:
    fund = db.get(Fund, code)
    if not fund:
        raise ValueError(f"基金代码 {code} 不存在")
    return fund


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, round(value, 2)))


def _persist_fund(db: Session, payload: ExternalFundPayload) -> Fund:
    fund = db.get(Fund, payload.code)
    if not fund:
        fund = Fund(code=payload.code)
        db.add(fund)
    fund.name = payload.name
    fund.fund_type = payload.fund_type
    fund.risk_level = payload.risk_level
    fund.theme = payload.theme
    fund.company = payload.company
    fund.latest_nav = payload.latest_nav or 0.0
    fund.estimated_nav = payload.estimated_nav or fund.latest_nav
    fund.estimated_change_rate = payload.estimated_change_rate or 0.0
    fund.latest_volume_rank = 0
    db.commit()
    db.refresh(fund)
    return fund


def _ensure_fund(db: Session, code: str) -> Fund:
    local_fund = db.get(Fund, code)
    if local_fund and (
        local_fund.name != code or local_fund.latest_nav > 0 or local_fund.fund_type != "未知类型"
    ):
        return local_fund
    payload = fetch_fund_profile(code)
    return _persist_fund(db, payload)


def _moving_average(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    if len(values) < period:
        return sum(values) / len(values)
    window = values[-period:]
    return sum(window) / len(window)


def _ema(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    alpha = 2 / float(period + 1)
    ema_values = [values[0]]
    last = values[0]
    for value in values[1:]:
        last = value * alpha + last * (1 - alpha)
        ema_values.append(last)
    return ema_values


def _macd(values: List[float]) -> Tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    dif_values = [short - long for short, long in zip(ema12, ema26)]
    dea_values = _ema(dif_values, 9)
    dif = dif_values[-1] if dif_values else 0.0
    dea = dea_values[-1] if dea_values else 0.0
    hist = (dif - dea) * 2
    return round(dif, 4), round(dea, 4), round(hist, 4)


def _kdj(values: List[float], period: int = 9) -> Tuple[float, float, float]:
    if not values:
        return 50.0, 50.0, 50.0
    k = 50.0
    d = 50.0
    for index, close in enumerate(values):
        start = max(0, index - period + 1)
        window = values[start : index + 1]
        high = max(window)
        low = min(window)
        if high == low:
            rsv = 50.0
        else:
            rsv = (close - low) / (high - low) * 100
        k = (2 * k + rsv) / 3
        d = (2 * d + k) / 3
    j = 3 * k - 2 * d
    return round(k, 2), round(d, 2), round(j, 2)


def _window_return(values: List[float], days: int) -> float:
    if len(values) <= days:
        return 0.0
    base = values[-days - 1]
    latest = values[-1]
    if base <= 0:
        return 0.0
    return round((latest / base - 1) * 100, 2)


def _max_drawdown(values: List[float], window: int = 60) -> float:
    if not values:
        return 0.0
    peak = values[-window] if len(values) >= window else values[0]
    max_drawdown = 0.0
    for value in values[-window:]:
        peak = max(peak, value)
        if peak <= 0:
            continue
        drawdown = (value - peak) / peak * 100
        max_drawdown = min(max_drawdown, drawdown)
    return round(abs(max_drawdown), 2)


def _format_signed_pct(value: float) -> str:
    return f"{value:+.2f}%"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _event_impact_score(event: Dict[str, Any]) -> float:
    sentiment = str(event.get("sentiment", "") or "")
    channel = str(event.get("channel", "") or "")
    if sentiment == "偏多":
        base = 9.0
    elif sentiment == "偏空":
        base = -9.0
    else:
        base = 2.0
    if channel == "公告":
        base *= 0.9
    elif channel == "板块":
        base *= 1.0
    elif channel == "国家队":
        base *= 1.15
    return base


def _build_trend_chart(metrics: Dict[str, Any], events: List[Dict[str, Any]]) -> Optional[TrendChartPayload]:
    nav_source = metrics.get("nav_series") or []
    if not nav_source:
        return None

    recent_nav = nav_source[-30:]
    nav_points: List[TrendChartPoint] = []
    date_sequence: List[datetime] = []
    for item in recent_nav:
        date_text = str(item.get("date", "") or "")
        dt = _parse_dt(date_text)
        nav_value = float(item.get("value", 0.0) or 0.0)
        if not dt or nav_value <= 0:
            continue
        date_sequence.append(dt)
        nav_points.append(
            TrendChartPoint(
                date=dt.strftime("%Y-%m-%d"),
                value=round(nav_value, 4),
                label=dt.strftime("%m-%d"),
            )
        )

    if not nav_points or not date_sequence:
        return None

    start_date = date_sequence[0].date()
    end_date = date_sequence[-1].date()
    daily_delta: Dict[str, float] = {}
    chart_events: List[TrendChartEvent] = []
    for event in events:
        dt = _parse_dt(event.get("published_at"))
        if not dt:
            continue
        event_date = dt.date()
        if event_date < start_date or event_date > end_date:
            continue
        key = event_date.strftime("%Y-%m-%d")
        daily_delta[key] = daily_delta.get(key, 0.0) + _event_impact_score(event)
        chart_events.append(
            TrendChartEvent(
                date=key,
                title=str(event.get("title", "") or ""),
                channel=event.get("channel"),
                sentiment=event.get("sentiment"),
            )
        )

    chart_events = chart_events[-5:]
    theme_points: List[TrendChartPoint] = []
    strength = 50.0
    current_date = start_date
    end_limit = end_date
    strength_by_date: Dict[str, float] = {}
    while current_date <= end_limit:
        key = current_date.strftime("%Y-%m-%d")
        delta = daily_delta.get(key, 0.0)
        # 让强度随时间缓慢回归中性，再叠加当天事件影响。
        strength = max(5.0, min(95.0, strength * 0.92 + 50.0 * 0.08 + delta))
        strength_by_date[key] = round(strength, 2)
        current_date += timedelta(days=1)

    for item in nav_points:
        theme_points.append(
            TrendChartPoint(
                date=item.date,
                value=strength_by_date.get(item.date, 50.0),
                label=item.label,
            )
        )

    return TrendChartPayload(
        nav_series=nav_points,
        theme_series=theme_points,
        event_points=chart_events,
    )


def _to_tencent_symbol(raw_code: str) -> Optional[str]:
    raw = str(raw_code or "").strip()
    if not raw:
        return None
    if "." in raw:
        market, digits = raw.split(".", 1)
        digits = re.sub(r"\D", "", digits).zfill(6)
        if not digits:
            return None
        return ("sh" if market == "1" else "sz") + digits
    digits = re.sub(r"\D", "", raw)[-6:]
    if not digits:
        return None
    return ("sh" if digits.startswith(("5", "6", "9")) else "sz") + digits


def _fetch_stock_quote_proxy(stock_codes: List[str]) -> Dict[str, float]:
    symbols = [symbol for symbol in (_to_tencent_symbol(code) for code in stock_codes) if symbol]
    if not symbols:
        return {"breadth": 0.0, "avg_change": 0.0, "avg_turnover_eok": 0.0, "count": 0.0}
    request = Request(
        TENCENT_QUOTE_URL + ",".join(symbols[:10]),
        headers={"User-Agent": TENCENT_USER_AGENT, "Referer": "https://gu.qq.com/"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = response.read().decode("gbk", errors="ignore")
    except Exception:
        return {"breadth": 0.0, "avg_change": 0.0, "avg_turnover_eok": 0.0, "count": 0.0}

    change_rates: List[float] = []
    turnovers: List[float] = []
    for line in payload.split(";"):
        if not line.strip():
            continue
        parts = line.split("~")
        if len(parts) < 38:
            continue
        try:
            change_rates.append(float(parts[32]))
        except (TypeError, ValueError):
            continue
        try:
            turnovers.append(float(parts[37]) / 10000.0)
        except (TypeError, ValueError):
            turnovers.append(0.0)
    if not change_rates:
        return {"breadth": 0.0, "avg_change": 0.0, "avg_turnover_eok": 0.0, "count": 0.0}
    positive_count = len([item for item in change_rates if item > 0])
    return {
        "breadth": round(positive_count / len(change_rates) * 100, 2),
        "avg_change": round(sum(change_rates) / len(change_rates), 2),
        "avg_turnover_eok": round(sum(turnovers) / max(len(turnovers), 1), 2),
        "count": float(len(change_rates)),
    }


def _build_technical_snapshot(metrics: Dict[str, Any]) -> Dict[str, Any]:
    nav_series = metrics.get("nav_series") or []
    nav_values = [float(item.get("nav", 0.0)) for item in nav_series if float(item.get("nav", 0.0)) > 0]
    if len(nav_values) < 30:
        return {
            "score": 50.0,
            "hint": "净值历史样本不足，技术面按保守权重处理",
            "signals": [
                {
                    "title": "技术面样本不足",
                    "text": "当前可用净值历史不足 30 个交易日，MACD/KDJ/均线仅做弱参考。",
                    "meta": "样本不足",
                }
            ],
            "trend_label": "样本不足",
            "is_overheated": False,
            "trigger_text": "等更多历史数据补齐后再观察。",
        }

    latest_nav = nav_values[-1]
    ma5 = _moving_average(nav_values, 5)
    ma10 = _moving_average(nav_values, 10)
    ma20 = _moving_average(nav_values, 20)
    ret5 = _window_return(nav_values, 5)
    ret10 = _window_return(nav_values, 10)
    ret20 = _window_return(nav_values, 20)
    drawdown60 = _max_drawdown(nav_values, 60)
    dif, dea, hist = _macd(nav_values)
    k_value, d_value, j_value = _kdj(nav_values, 9)

    position_series = metrics.get("position_series") or []
    recent_position = float(position_series[-1].get("position", 0.0)) if position_series else 0.0
    past_position = float(position_series[-5].get("position", recent_position)) if len(position_series) >= 5 else recent_position
    position_delta = round(recent_position - past_position, 2)

    volume_proxy = _fetch_stock_quote_proxy(metrics.get("stock_codes") or [])
    breadth = float(volume_proxy.get("breadth", 0.0))
    avg_change = float(volume_proxy.get("avg_change", 0.0))
    avg_turnover = float(volume_proxy.get("avg_turnover_eok", 0.0))

    score = 52.0
    trend_label = "震荡整理"
    if ma5 >= ma10 >= ma20 and latest_nav >= ma10:
        score += 15
        trend_label = "均线多头"
    elif latest_nav >= ma20 and ma5 >= ma10:
        score += 8
        trend_label = "震荡偏强"
    elif latest_nav < ma20 and ma5 < ma10:
        score -= 12
        trend_label = "趋势偏弱"

    if dif >= dea and hist >= 0:
        score += 10
    elif dif >= dea:
        score += 4
    else:
        score -= 9

    is_overheated = False
    if j_value <= 20 and k_value > d_value:
        score += 8
    elif j_value >= 88 and k_value < d_value:
        score -= 8
        is_overheated = True
    elif k_value > d_value:
        score += 3
    else:
        score -= 2

    if ret20 > 8:
        score += 5
    elif ret20 > 0:
        score += 2
    elif ret20 < -8:
        score -= 8

    if drawdown60 <= 8:
        score += 5
    elif drawdown60 >= 18:
        score -= 8

    if breadth >= 60 and avg_change > 0.5:
        score += 6
    elif breadth <= 35 and avg_change < 0:
        score -= 6

    if position_delta >= 4:
        score += 3
    elif position_delta <= -4:
        score -= 3

    score = _clamp(score)
    hint_parts: List[str] = []
    hint_parts.append("MACD 偏多" if dif >= dea else "MACD 偏弱")
    hint_parts.append("KDJ 低位抬头" if j_value <= 25 and k_value > d_value else "KDJ 高位震荡" if j_value >= 80 else "KDJ 中性")
    hint_parts.append(trend_label)
    hint = " / ".join(hint_parts[:3])

    signals = [
        {
            "title": "均线结构",
            "text": f"最新净值 {latest_nav:.4f}，5/10/20 日均线分别为 {ma5:.4f} / {ma10:.4f} / {ma20:.4f}，当前属于“{trend_label}”结构。",
            "meta": f"MA5 {ma5:.4f} | MA10 {ma10:.4f} | MA20 {ma20:.4f}",
        },
        {
            "title": "MACD 信号",
            "text": f"DIF {dif:.4f}、DEA {dea:.4f}、柱体 {hist:.4f}，当前{'形成多头动能' if dif >= dea else '动能仍偏弱'}。",
            "meta": "MACD",
        },
        {
            "title": "KDJ 摆动",
            "text": f"K {k_value:.2f} / D {d_value:.2f} / J {j_value:.2f}，当前{'短线偏热，追高性价比下降' if j_value >= 88 else '存在低位修复迹象' if j_value <= 20 else '处于中性偏观察区间'}。",
            "meta": "KDJ",
        },
        {
            "title": "阶段动量",
            "text": f"近 5 日 {ret5:+.2f}% 、近 10 日 {ret10:+.2f}% 、近 20 日 {ret20:+.2f}% ，60 日最大回撤 {drawdown60:.2f}%。",
            "meta": "动量/回撤",
        },
        {
            "title": "量能代理",
            "text": (
                f"基于前十大重仓股实时涨跌与成交额做代理，红盘占比 {breadth:.0f}% ，平均涨跌 {avg_change:+.2f}% ，"
                f"平均成交额约 {avg_turnover:.2f} 亿。"
            ),
            "meta": "成分股成交热度",
        },
        {
            "title": "仓位活跃度",
            "text": f"最近基金股票仓位测算变化 {position_delta:+.2f}pct，当前权益仓位约 {recent_position:.2f}%。",
            "meta": "股票仓位测算",
        },
    ]

    if is_overheated:
        trigger_text = "优先等 5 日均线附近或 KDJ 回落后再看二次上车。"
    elif dif >= dea and k_value > d_value:
        trigger_text = "可等待回踩不破 10 日均线时再做分批介入。"
    else:
        trigger_text = "先等 MACD 再度走强或近 10 日收益重新翻正。"

    return {
        "score": score,
        "hint": hint,
        "signals": signals,
        "trend_label": trend_label,
        "is_overheated": is_overheated,
        "trigger_text": trigger_text,
    }


def _build_trade_advices(
    fund: Fund,
    decision: str,
    technical_snapshot: Dict[str, Any],
    holding: Optional[PortfolioHolding],
) -> Tuple[List[Dict[str, str]], Optional[Dict[str, str]]]:
    estimated_nav = float(fund.estimated_nav or fund.latest_nav or 0.0)
    market_value = round(float(holding.shares) * estimated_nav, 2) if holding and estimated_nav > 0 else 0.0
    holding_profit = round(market_value - float(holding.cost_amount), 2) if holding else 0.0
    holding_profit_rate = round(holding_profit / float(holding.cost_amount) * 100, 2) if holding and holding.cost_amount > 0 else 0.0

    if decision == "建议买入":
        today_action = "今日可以试探建仓，但不建议一次性满仓。"
        position_action = "首笔仓位控制在计划仓位的 20%-30%，回踩不破 10 日均线时再补第二笔。"
    elif decision == "可分批关注":
        today_action = "更适合挂观察清单，等回踩或量能确认后再动手。"
        position_action = "若一定要参与，建议两笔分开，单笔不超过计划仓位的 15%-20%。"
    elif decision == "观察中":
        today_action = "暂不建议追价，优先等待技术面重新转强。"
        position_action = "保持轻仓观察，除非 MACD 与 KDJ 同步改善。"
    else:
        today_action = "今天不建议新增仓位，优先控制回撤。"
        position_action = "把操作重点放在减仓、止盈或等待更清晰信号。"

    trigger_action = technical_snapshot.get("trigger_text", "等待下一次明确技术信号。")
    advices = [
        {"title": "今日操作", "text": today_action, "meta": fund.code},
        {"title": "仓位节奏", "text": position_action, "meta": "分批执行"},
        {"title": "触发条件", "text": trigger_action, "meta": technical_snapshot.get("trend_label", "技术触发")},
    ]

    if not holding:
        return advices, {
            "title": "当前未持仓",
            "text": "系统没有检测到你在组合中的这只基金持仓，综合建议会按“新开仓场景”生成。",
            "meta": "未持仓",
        }

    if decision in {"建议买入", "可分批关注"} and holding_profit_rate < 0:
        position_text = f"你当前已持仓约 {market_value:,.2f} 元，累计收益 {holding_profit:+.2f} 元（{holding_profit_rate:+.2f}%）。若继续看多，只建议小幅补仓，不要摊大成本。"
    elif decision in {"建议买入", "可分批关注"} and holding_profit_rate >= 8:
        position_text = f"你当前已持仓约 {market_value:,.2f} 元，累计收益 {holding_profit:+.2f} 元（{holding_profit_rate:+.2f}%）。已有浮盈时更适合等回踩再加，不建议盘中追高。"
    elif decision in {"观察中", "暂时观望", "不建议当前买入"} and holding_profit_rate > 0:
        position_text = f"你当前仍有浮盈 {holding_profit:+.2f} 元（{holding_profit_rate:+.2f}%），若技术面继续转弱，可考虑分批止盈锁定收益。"
    else:
        position_text = f"你当前持仓市值约 {market_value:,.2f} 元，累计收益 {holding_profit:+.2f} 元（{holding_profit_rate:+.2f}%），更适合先守仓观察，不要频繁来回操作。"

    return advices, {
        "title": "持仓联动建议",
        "text": position_text,
        "meta": f"持仓 {market_value:,.2f} 元",
    }


def _build_generated_analysis_payload(db: Session, fund: Fund, metrics: Dict[str, Any]) -> Dict[str, Any]:
    one_month = float(metrics.get("one_month_return", 0.0))
    three_month = float(metrics.get("three_month_return", 0.0))
    six_month = float(metrics.get("six_month_return", 0.0))
    one_year = float(metrics.get("one_year_return", 0.0))
    scale_mom = float(metrics.get("scale_mom", 0.0))
    manager_name = metrics.get("manager_name") or "基金经理"
    manager_star = float(metrics.get("manager_star", 0.0))
    risk_level = fund.risk_level
    message_snapshot = fetch_message_snapshot(
        fund_name=fund.name,
        code=fund.code,
        theme=fund.theme,
        company=fund.company,
    )
    message_delta = float(message_snapshot.get("score_delta", 0.0))
    announcement_events = message_snapshot.get("announcement_events", [])
    news_events = message_snapshot.get("news_events", [])
    theme_events = message_snapshot.get("theme_events", [])
    national_team_events = message_snapshot.get("national_team_events", [])
    all_message_events = message_snapshot.get("events", [])
    technical_snapshot = _build_technical_snapshot(metrics)
    holding = db.scalar(select(PortfolioHolding).where(PortfolioHolding.fund_code == fund.code))

    risk_penalty_map = {"低": 8, "中低": 18, "中": 25, "中高": 38, "高": 48}
    risk_penalty = next((value for key, value in risk_penalty_map.items() if key == risk_level), 30)

    technical_score = technical_snapshot["score"]
    news_score = _clamp(
        50
        + max(scale_mom, 0) * 1.1
        + manager_star * 3.5
        - max(-scale_mom, 0) * 1.0
        + message_delta
        + len(theme_events) * 1.8
        + len(national_team_events) * 2.2
    )
    risk_score = _clamp(88 - risk_penalty - abs(one_month) * 0.4 - abs(three_month) * 0.15, 18, 88)
    score = _clamp(technical_score * 0.4 + news_score * 0.35 + risk_score * 0.25)

    if score >= 80 and not technical_snapshot.get("is_overheated"):
        decision, action, confidence = "建议买入", "分两笔布局", "中高"
    elif score >= 68:
        decision, action, confidence = "可分批关注", "等待回踩再分批介入", "中"
    elif score >= 58:
        decision, action, confidence = "观察中", "先跟踪信号再决定", "中"
    else:
        decision, action, confidence = "暂时观望", "不追高，控制回撤", "中低"

    holding_window = "1-3 周" if technical_snapshot.get("trend_label") in {"均线多头", "震荡偏强"} else "继续观察 3-5 个交易日"
    summary_title = f"{decision}，已结合多指标技术面、主题消息与持仓情况生成当日建议"
    trade_advices, position_note = _build_trade_advices(fund, decision, technical_snapshot, holding)

    reasons = {
        "summary": [
            {"title": "多指标技术面已纳入", "text": technical_snapshot.get("hint", "技术面已纳入均线、MACD、KDJ 和量能代理。")},
            {"title": "阶段趋势基础", "text": f"近 1 月 {one_month:.2f}% 、近 3 月 {three_month:.2f}% 、近 6 月 {six_month:.2f}% 。"},
            {"title": "多通道消息面已纳入", "text": message_snapshot.get("reason_text", "最近暂无公告或新闻。")},
            trade_advices[0],
        ],
        "technical": technical_snapshot.get("signals", []),
        "news": [
            {"title": f"基金经理：{manager_name}", "text": f"基金经理星级 {manager_star:.0f}，已纳入当前初版评分。"},
            {"title": "规模变化纳入消息面因子", "text": f"最近一期规模变化 {scale_mom:.2f}% ，用于辅助判断资金承接情况。"},
            {"title": "真实公告已纳入消息面", "text": build_message_reason_text(announcement_events)},
            {"title": "真实新闻已纳入消息面", "text": build_message_reason_text(news_events)},
            {"title": "板块/主题动态", "text": build_message_reason_text(theme_events)},
            {"title": "国家队加减仓线索", "text": build_message_reason_text(national_team_events)},
        ],
    }
    events = [
        {
            "title": "消息面多通道概览",
            "meta": (
                f"公告 {len(announcement_events)} 条 | 基金新闻 {len(news_events)} 条 | "
                f"板块动态 {len(theme_events)} 条 | 国家队线索 {len(national_team_events)} 条"
            ),
            "channel": "系统",
            "source": "Funding消息编排",
        },
        *build_event_cards(all_message_events),
    ]
    risks = [
        {"title": "消息面并非完整内幕信息", "text": "当前已接入真实公告、相关新闻、板块动态与国家队关键词检索，但仍需结合更多公开信息交叉确认。"},
        {"title": "基金类型和风险等级需结合自身偏好", "text": f"该基金类型为 {fund.fund_type}，风险等级 {fund.risk_level}。"},
        {"title": "场外基金技术面天然滞后", "text": "MACD / KDJ 基于净值序列推导，不等同于股票分时交易信号，适合辅助判断节奏。"},
    ]
    if technical_snapshot.get("is_overheated"):
        risks.append({"title": "短线偏热", "text": "KDJ 已进入高位区，当前更适合等回踩后再判断，不建议情绪化追高。"})
    if position_note:
        risks.append({"title": position_note["title"], "text": position_note["text"]})

    summary_text = generate_ai_summary(
        {
            "fund_name": fund.name,
            "fund_code": fund.code,
            "decision": decision,
            "score": score,
            "technical_score": technical_score,
            "news_score": news_score,
            "risk_score": risk_score,
            "one_month_return": one_month,
            "three_month_return": three_month,
            "one_year_return": one_year,
            "manager_name": manager_name,
            "manager_star": manager_star,
            "events": events,
            "risks": risks,
            "trade_advices": trade_advices,
            "position_note": position_note,
            "technical_hint": technical_snapshot.get("hint", ""),
            "news_reason": message_snapshot.get("reason_text", ""),
        }
    )
    return {
        "fund_code": fund.code,
        "decision": decision,
        "confidence": confidence,
        "action": action,
        "holding_window": holding_window,
        "score": score,
        "technical_score": technical_score,
        "news_score": news_score,
        "risk_score": risk_score,
        "summary_title": summary_title,
        "summary_text": summary_text,
        "reasons_json": json.dumps(reasons, ensure_ascii=False),
        "events_json": json.dumps(events, ensure_ascii=False),
        "risks_json": json.dumps(risks, ensure_ascii=False),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "technical_signals": technical_snapshot.get("signals", []),
        "trade_advices": trade_advices,
        "position_note": position_note,
        "technical_hint": technical_snapshot.get("hint", "技术面评分"),
        "news_hint": message_snapshot.get("signal_text", message_snapshot.get("reason_text", "消息面评分")),
        "risk_hint": "结合基金波动、风险等级与当前仓位生成",
        "message_snapshot": message_snapshot,
    }


def _ensure_analysis_snapshot(db: Session, fund: Fund) -> Tuple[FundAnalysisSnapshot, Dict[str, Any]]:
    payload = fetch_fund_profile(fund.code)
    _persist_fund(db, payload)
    snapshot = db.scalar(
        select(FundAnalysisSnapshot)
        .where(FundAnalysisSnapshot.fund_code == fund.code)
        .order_by(FundAnalysisSnapshot.id.desc())
        .limit(1)
    )
    generated_payload = _build_generated_analysis_payload(db, fund, payload.metrics)
    storage_payload = {key: value for key, value in generated_payload.items() if key in SNAPSHOT_KEYS}
    if snapshot:
        for key, value in storage_payload.items():
            setattr(snapshot, key, value)
        generated_snapshot = snapshot
    else:
        generated_snapshot = FundAnalysisSnapshot(**storage_payload)
        db.add(generated_snapshot)
    db.commit()
    db.refresh(generated_snapshot)
    return generated_snapshot, generated_payload


def get_fund_detail(db: Session, code: str) -> FundDetail:
    fund = _ensure_fund(db, code)
    return FundDetail.model_validate(fund, from_attributes=True)


def get_fund_analysis(db: Session, code: str) -> FundAnalysisResponse:
    fund = _ensure_fund(db, code)
    snapshot, generated_payload = _ensure_analysis_snapshot(db, fund)
    profile_payload = fetch_fund_profile(fund.code)
    message_snapshot = generated_payload.get("message_snapshot", {})

    reasons = {
        key: [AnalysisItem(**item) for item in value]
        for key, value in json.loads(snapshot.reasons_json).items()
    }
    announcement_events = [AnalysisItem(**item) for item in message_snapshot.get("announcement_events", [])[:5]]
    news_events = [AnalysisItem(**item) for item in message_snapshot.get("news_events", [])[:5]]
    events = [AnalysisItem(**item) for item in json.loads(snapshot.events_json)]
    risks = [AnalysisItem(**item) for item in json.loads(snapshot.risks_json)]
    technical_signals = [AnalysisItem(**item) for item in generated_payload.get("technical_signals", [])]
    trade_advices = [AnalysisItem(**item) for item in generated_payload.get("trade_advices", [])]
    position_note = generated_payload.get("position_note")
    trend_chart = _build_trend_chart(profile_payload.metrics, message_snapshot.get("all_events", []))

    return FundAnalysisResponse(
        fund=FundDetail.model_validate(fund, from_attributes=True),
        decision=snapshot.decision,
        confidence=snapshot.confidence,
        action=snapshot.action,
        holding_window=snapshot.holding_window,
        score=snapshot.score,
        technical=ScoreSummary(score=snapshot.technical_score, hint=generated_payload.get("technical_hint", "技术面评分")),
        news=ScoreSummary(score=snapshot.news_score, hint=generated_payload.get("news_hint", "消息面评分")),
        risk=ScoreSummary(score=snapshot.risk_score, hint=generated_payload.get("risk_hint", "风险评分")),
        summary_title=snapshot.summary_title,
        summary_text=snapshot.summary_text,
        reasons=reasons,
        announcement_events=announcement_events,
        news_events=news_events,
        events=events,
        risks=risks,
        technical_signals=technical_signals,
        trade_advices=trade_advices,
        position_note=AnalysisItem(**position_note) if position_note else None,
        trend_chart=trend_chart,
        updated_at=snapshot.updated_at,
    )
