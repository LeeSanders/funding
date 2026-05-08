import json
from typing import Any, Dict, List
from urllib.request import Request, urlopen

from app.core.config import settings


def _fallback_summary(payload: Dict[str, Any]) -> str:
    fund_name = payload["fund_name"]
    code = payload["fund_code"]
    decision = payload["decision"]
    score = payload["score"]
    technical = payload["technical_score"]
    news = payload["news_score"]
    risk = payload["risk_score"]
    latest_event = "最近没有抓到明显公告或新闻"
    for event in payload["events"]:
        title = event.get("title", "")
        channel = event.get("channel", "")
        if channel in {"公告", "新闻", "板块", "国家队"} and title:
            latest_event = title
            break
    advice = ""
    trade_advices = payload.get("trade_advices") or []
    if trade_advices:
        advice = trade_advices[0].get("text", "")
    position_note = payload.get("position_note") or {}
    position_text = position_note.get("text", "当前按未持仓场景处理。")
    return (
        f"{fund_name}（{code}）当前综合评分 {score:.1f} 分，结论为“{decision}”。"
        f"技术面 {technical:.1f} 分，消息面 {news:.1f} 分，风险分 {risk:.1f} 分。"
        f"最近消息面重点是：{latest_event}。"
        f"{advice or '今天更适合按分批、等待确认的节奏处理。'}"
        f"{position_text}"
        "以上仅供研究辅助，不构成投资建议。"
    )


def generate_ai_summary(payload: Dict[str, Any]) -> str:
    if not settings.llm_api_key or not settings.llm_base_url or not settings.llm_model:
        return _fallback_summary(payload)

    prompt = (
        "你是基金分析助手。请根据给定的基金基础信息、技术面评分、消息面评分、风险评分、真实公告新闻板块国家队事件、"
        "以及用户当前持仓情况，生成 160 字以内的中文投资辅助总结。"
        "要求：1. 明确今天偏买入、观望还是卖出；2. 点出核心依据；3. 给出一条可执行操作建议；"
        "4. 强调风险；5. 不要承诺收益；6. 语气专业克制。"
    )
    body = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0.3,
    }
    request = Request(
        f"{settings.llm_base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.llm_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        return payload["choices"][0]["message"]["content"].strip()
    except Exception:
        return _fallback_summary(payload)
