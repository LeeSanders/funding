import json
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import FundAnalysisSnapshot
from app.models.fund import Fund
from app.schemas.recommendation import RecommendationFactor, RecommendationItem, RecommendationResponse
from app.services import fund_service
from app.services.external_fund_service import fetch_top_gainer_fund_candidates


STRATEGY_CONFIG = {
    "steady": {
        "title": "稳健型推荐逻辑",
        "description": "先从东财热门权益基金里挑出回撤更可控、消息面没有明显负反馈的标的。",
        "weights": {"technical": 0.20, "news": 0.20, "risk": 0.60},
        "methodology": "优先看风险控制与持有体验，再考虑趋势和消息是否提供辅助增强。",
        "scoring_rule": "推荐分 = 技术面 20% + 消息面 20% + 风险承受度 60%",
        "suitable_for": "适合把回撤和组合稳定放在第一位的用户。",
        "dimensions": ["最大回撤容忍", "波动稳定性", "消息扰动强弱", "配置防守性"],
    },
    "aggressive": {
        "title": "进取型推荐逻辑",
        "description": "先从东财热门权益基金里挑出趋势和消息共振更强、弹性更高的标的。",
        "weights": {"technical": 0.40, "news": 0.45, "risk": 0.15},
        "methodology": "优先抓趋势和催化共振，再接受更高波动。",
        "scoring_rule": "推荐分 = 技术面 40% + 消息面 45% + 风险承受度 15%",
        "suitable_for": "适合愿意承担更高波动、优先追踪强势方向的观察场景。",
        "dimensions": ["短中期动量", "催化密度", "主题景气", "风险容忍"],
    },
}

RECOMMENDATION_CACHE_TTL = timedelta(minutes=10)
RECOMMENDATION_CANDIDATE_LIMIT = 12
_RECOMMENDATION_CACHE: Dict[str, Dict[str, object]] = {}


def _safe_reason_text(items: list, fallback: str, excluded_keywords: Optional[List[str]] = None) -> str:
    excluded_keywords = excluded_keywords or []
    if not items:
        return fallback
    for item in items:
        text = getattr(item, "text", "") or ""
        if text and not any(keyword in text for keyword in excluded_keywords):
            return text
    return fallback


def _recommend_reason(seed_reason: str, technical_reason: str, message_reason: str) -> str:
    return f"{seed_reason}，技术面看 {technical_reason}；消息面看 {message_reason}"


def _cache_is_fresh(strategy_key: str) -> bool:
    cached = _RECOMMENDATION_CACHE.get(strategy_key)
    if not cached:
        return False
    generated_at = cached.get("generated_at")
    if not isinstance(generated_at, datetime):
        return False
    return datetime.now() - generated_at <= RECOMMENDATION_CACHE_TTL


def _reason_text_from_snapshot(snapshot: FundAnalysisSnapshot, key: str, fallback: str) -> str:
    try:
        payload = json.loads(snapshot.reasons_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    rows = payload.get(key) or []
    for item in rows:
        text = str(item.get("text", "") or "").strip()
        if text and "已接入外部基金站点" not in text and "成功抓取" not in text:
            return text
    return fallback


def _risk_text_from_snapshot(snapshot: FundAnalysisSnapshot) -> str:
    try:
        rows = json.loads(snapshot.risks_json or "[]")
    except json.JSONDecodeError:
        rows = []
    if rows:
        return str(rows[0].get("text", "") or "").strip() or "暂无额外风险提示"
    return "暂无额外风险提示"


def _latest_snapshot_map(db: Session) -> Dict[str, FundAnalysisSnapshot]:
    rows = db.scalars(select(FundAnalysisSnapshot).order_by(FundAnalysisSnapshot.id.desc())).all()
    latest: Dict[str, FundAnalysisSnapshot] = {}
    for item in rows:
        if item.fund_code not in latest:
            latest[item.fund_code] = item
    return latest


def _build_recommendations(db: Session, strategy_key: str) -> RecommendationResponse:
    config = STRATEGY_CONFIG[strategy_key]
    weights = config["weights"]
    candidates = []
    snapshot_map = _latest_snapshot_map(db)

    for hot_item in fetch_top_gainer_fund_candidates(limit=RECOMMENDATION_CANDIDATE_LIMIT):
        snapshot = snapshot_map.get(hot_item.code)
        fund = db.get(Fund, hot_item.code)
        if snapshot and fund:
            technical_score = snapshot.technical_score
            news_score = snapshot.news_score
            risk_score = snapshot.risk_score
            weighted_score = round(
                technical_score * weights["technical"]
                + news_score * weights["news"]
                + risk_score * weights["risk"],
                2,
            )
            reason = _reason_text_from_snapshot(snapshot, "summary", snapshot.summary_text)
            technical_reason = _reason_text_from_snapshot(snapshot, "technical", "当前技术面依据不足")
            message_reason = _reason_text_from_snapshot(snapshot, "news", "当前消息面依据不足")
            risk = _risk_text_from_snapshot(snapshot)
            decision = snapshot.decision
            action = snapshot.action
            confidence = snapshot.confidence
            holding_window = snapshot.holding_window
            fund_code = fund.code
            fund_name = fund.name
        else:
            try:
                analysis = fund_service.get_fund_analysis(db, hot_item.code)
            except ValueError:
                continue
            weighted_score = round(
                analysis.technical.score * weights["technical"]
                + analysis.news.score * weights["news"]
                + analysis.risk.score * weights["risk"],
                2,
            )
            summary_reasons = analysis.reasons.get("summary", [])
            technical_reasons = analysis.reasons.get("technical", [])
            message_reasons = analysis.reasons.get("news", [])
            reason = _safe_reason_text(
                summary_reasons,
                analysis.summary_text,
                excluded_keywords=["已接入外部基金站点", "成功抓取"],
            )
            technical_reason = _safe_reason_text(technical_reasons, "当前技术面依据不足")
            message_reason = _safe_reason_text(
                list(reversed(message_reasons)),
                "当前消息面依据不足",
                excluded_keywords=["基金经理星级", "规模变化"],
            )
            risk = analysis.risks[0].text if analysis.risks else "暂无额外风险提示"
            technical_score = analysis.technical.score
            news_score = analysis.news.score
            risk_score = analysis.risk.score
            decision = analysis.decision
            action = analysis.action
            confidence = analysis.confidence
            holding_window = analysis.holding_window
            fund_code = analysis.fund.code
            fund_name = analysis.fund.name
        seed_reason = f"当日表现 {hot_item.daily_change:+.2f}% ，所属板块 {hot_item.board}"
        strategy_reason = _recommend_reason(seed_reason, technical_reason, message_reason)
        candidates.append(
            {
                "fund_code": fund_code,
                "fund_name": fund_name,
                "decision": decision,
                "action": action,
                "score": weighted_score,
                "confidence": confidence,
                "holding_window": holding_window,
                "suitable_for": config["suitable_for"],
                "reason": reason,
                "strategy_reason": strategy_reason,
                "technical_reason": technical_reason,
                "message_reason": message_reason,
                "risk": risk,
                "hot_reason": seed_reason,
                "technical_score": technical_score,
                "news_score": news_score,
                "risk_score": risk_score,
                "factors": [
                    RecommendationFactor(
                        name="技术面",
                        score=technical_score,
                        text=technical_reason,
                    ),
                    RecommendationFactor(
                        name="消息面",
                        score=news_score,
                        text=message_reason,
                    ),
                    RecommendationFactor(
                        name="风险承受度",
                        score=risk_score,
                        text=risk,
                    ),
                ],
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    items = [
        RecommendationItem(
            rank=index,
            fund_code=item["fund_code"],
            fund_name=item["fund_name"],
            decision=item["decision"],
            action=item["action"],
            score=item["score"],
            confidence=item["confidence"],
            holding_window=item["holding_window"],
            suitable_for=item["suitable_for"],
            reason=item["reason"],
            strategy_reason=item["strategy_reason"],
            technical_reason=item["technical_reason"],
            message_reason=item["message_reason"],
            risk=item["risk"],
            hot_reason=item["hot_reason"],
            technical_score=item["technical_score"],
            news_score=item["news_score"],
            risk_score=item["risk_score"],
            factors=item["factors"],
        )
        for index, item in enumerate(candidates[:RECOMMENDATION_CANDIDATE_LIMIT], start=1)
    ]

    return RecommendationResponse(
        strategy=strategy_key,
        title=config["title"],
        description=config["description"],
        methodology=config["methodology"],
        scoring_rule=config["scoring_rule"],
        suitable_for=config["suitable_for"],
        dimensions=config["dimensions"],
        items=items,
    )


def get_recommendations(db: Session, strategy: str) -> RecommendationResponse:
    strategy_key = strategy if strategy in STRATEGY_CONFIG else "steady"
    if _cache_is_fresh(strategy_key):
        return deepcopy(_RECOMMENDATION_CACHE[strategy_key]["response"])

    try:
        response = _build_recommendations(db, strategy_key)
        _RECOMMENDATION_CACHE[strategy_key] = {
            "generated_at": datetime.now(),
            "response": deepcopy(response),
        }
        return response
    except Exception:
        cached = _RECOMMENDATION_CACHE.get(strategy_key)
        if cached and cached.get("response"):
            return deepcopy(cached["response"])
        raise
