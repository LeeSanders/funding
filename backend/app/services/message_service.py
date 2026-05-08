from datetime import datetime, timedelta
import html
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import json


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _fetch_json(url: str) -> Dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Referer": "https://fundf10.eastmoney.com/"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def _fetch_text(url: str, referer: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Referer": referer})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="ignore")


def _classify_announcement(title: str) -> Dict[str, Any]:
    positive_words = ["分红", "增聘", "开放申购", "获批", "成立", "上涨", "回升"]
    risk_words = ["暂停", "终止", "清算", "离任", "下调", "风险", "异常", "赎回", "限购"]
    neutral_words = ["季度报告", "年度报告", "提示性公告", "服务提示", "招募说明书"]

    if any(keyword in title for keyword in risk_words):
        return {"label": "偏空", "delta": -8}
    if any(keyword in title for keyword in positive_words):
        return {"label": "偏多", "delta": 8}
    if any(keyword in title for keyword in neutral_words):
        return {"label": "中性", "delta": 2}
    return {"label": "中性", "delta": 0}


def _classify_news(title: str, content: str) -> Dict[str, Any]:
    text = f"{title} {content}"
    positive_words = ["增持", "上涨", "创新高", "回升", "盈利", "利润增长", "超预期", "景气", "受益", "看好"]
    risk_words = ["下跌", "亏损", "回撤", "风险", "终止", "清盘", "压力", "减持", "波动", "承压"]
    if any(keyword in text for keyword in risk_words):
        return {"label": "偏空", "delta": -6}
    if any(keyword in text for keyword in positive_words):
        return {"label": "偏多", "delta": 6}
    return {"label": "中性", "delta": 1}


def _strip_tags(text: str) -> str:
    return html.unescape(re.sub(r"<.*?>", "", text or "")).strip()


def _normalize_fund_name(name: str) -> str:
    return re.sub(r"[A-C]$", "", (name or "").strip())


def _event_sort_key(item: Dict[str, Any]) -> str:
    return item.get("published_at", "") or ""


def _parse_jsonp(payload: str) -> Dict[str, Any]:
    start = payload.find("(")
    end = payload.rfind(")")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("invalid jsonp payload")
    return json.loads(payload[start + 1 : end])


def _news_keyword_candidates(fund_name: str, code: str, theme: str, company: str) -> List[str]:
    base_name = _normalize_fund_name(fund_name)
    candidates = [f"{base_name} {code}", fund_name, base_name, code]
    seen: List[str] = []
    for item in candidates:
        item = item.strip()
        if item and item not in seen:
            seen.append(item)
    return seen[:3]


def _topic_candidates(fund_name: str, theme: str) -> List[str]:
    raw_candidates = [theme or "", _normalize_fund_name(fund_name)]
    common_words = [
        "混合",
        "股票",
        "指数",
        "增强",
        "联接",
        "发起式",
        "证券投资",
        "基金",
        "灵活配置",
        "A",
        "C",
    ]
    cleaned: List[str] = []
    for raw in raw_candidates:
        text = raw.strip()
        if not text:
            continue
        for word in common_words:
            text = text.replace(word, " ")
        parts = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
        for part in parts:
            if part not in cleaned:
                cleaned.append(part)
    return cleaned[:3]


def _sentiment_tone(events: List[Dict[str, Any]]) -> str:
    if not events:
        return "中性"
    score = 0
    for item in events:
        label = item.get("sentiment", "")
        if label == "偏多":
            score += 1
        elif label == "偏空":
            score -= 1
    if score >= 2:
        return "偏多"
    if score <= -2:
        return "偏空"
    return "中性"


def _issue_from_title(title: str, channel: str = "") -> str:
    text = title or ""
    keyword_map = [
        (("离任", "增聘", "基金经理", "任职"), "基金经理变化"),
        (("年报", "季报", "报告", "招募说明书"), "定期信息披露"),
        (("限购", "暂停申购", "暂停赎回", "开放申购", "开放赎回"), "申赎规则变化"),
        (("分红", "收益分配"), "分红安排"),
        (("规模", "份额", "申购", "赎回"), "资金流入流出"),
        (("政策", "会议", "发改委", "财政", "降准", "降息"), "政策预期变化"),
        (("景气", "回暖", "涨价", "需求", "订单", "盈利"), "行业景气度变化"),
        (("中央汇金", "国家队", "证金", "社保", "险资", "增持"), "大资金态度"),
        (("回撤", "承压", "波动", "风险", "减持", "下跌"), "风险扰动"),
    ]
    for keywords, issue in keyword_map:
        if any(keyword in text for keyword in keywords):
            return issue
    if channel == "公告":
        return "基金公告更新"
    if channel == "板块":
        return "板块情绪变化"
    if channel == "国家队":
        return "大资金态度"
    return "市场关注点变化"


def _channel_takeaway(events: List[Dict[str, Any]], channel_label: str) -> str:
    if not events:
        if channel_label == "国家队":
            return "暂未看到明确的大资金增减仓公开线索。"
        return f"暂未看到对{channel_label}有明确影响的公开信息。"
    latest = events[0]
    issue = _issue_from_title(latest.get("title", ""), latest.get("channel", channel_label))
    tone = _sentiment_tone(events)
    if channel_label == "公告":
        return f"公告主要反映“{issue}”，整体偏{tone}，说明基金层面的正式披露有更新。"
    if channel_label == "新闻":
        return f"相关新闻主要围绕“{issue}”，整体偏{tone}，说明市场当前关注点落在这条线上。"
    if channel_label == "板块":
        return f"板块消息集中在“{issue}”，整体偏{tone}，说明主题情绪正在发生变化。"
    if channel_label == "国家队":
        return f"国家队相关线索主要指向“{issue}”，整体偏{tone}，可用来观察大资金态度。"
    return f"最近信息主要集中在“{issue}”，整体偏{tone}。"


def _parse_event_datetime(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _recent_events(events: List[Dict[str, Any]], days: int = 2) -> List[Dict[str, Any]]:
    cutoff = datetime.now() - timedelta(days=days)
    result: List[Dict[str, Any]] = []
    for item in events:
        dt = _parse_event_datetime(item.get("published_at", ""))
        if not dt:
            continue
        if dt >= cutoff:
            result.append(item)
    return result


def _primary_issue(events: List[Dict[str, Any]]) -> str:
    if not events:
        return "缺少明确催化"
    counter: Dict[str, int] = {}
    for item in events:
        issue = _issue_from_title(item.get("title", ""), item.get("channel", ""))
        counter[issue] = counter.get(issue, 0) + 1
    return sorted(counter.items(), key=lambda x: (-x[1], x[0]))[0][0]


def _tone_advice(tone: str) -> str:
    if tone == "偏多":
        return "说明短线催化偏正面，但还要看持续性。"
    if tone == "偏空":
        return "说明短线压制更明显，今天更适合偏谨慎。"
    return "说明公开信息暂未形成明确单边结论。"


def _simple_tone_conclusion(tone: str, issue: str, channel: str) -> str:
    if channel == "板块":
        if tone == "偏多":
            return f"板块消息偏多，主要指向“{issue}”，短线情绪有支撑。"
        if tone == "偏空":
            return f"板块消息偏空，主要落在“{issue}”，短线更适合谨慎。"
        return f"板块消息中性，当前主要围绕“{issue}”，还没形成强催化。"
    if tone == "偏多":
        return f"消息面偏多，主要指向“{issue}”，短线有一定催化。"
    if tone == "偏空":
        return f"消息面偏空，主要落在“{issue}”，短线压制更明显。"
    return f"消息面中性，当前主要围绕“{issue}”，方向还不够清晰。"


def build_message_signal_text(
    announcement_events: List[Dict[str, Any]],
    news_events: List[Dict[str, Any]],
    theme_events: List[Dict[str, Any]],
    national_team_events: List[Dict[str, Any]],
) -> str:
    recent_theme = _recent_events(theme_events, days=2) or theme_events
    if recent_theme:
        board_tone = _sentiment_tone(recent_theme)
        board_issue = _primary_issue(recent_theme)
        return _simple_tone_conclusion(board_tone, board_issue, "板块")

    recent_news = _recent_events(news_events, days=2) or news_events
    if recent_news:
        news_tone = _sentiment_tone(recent_news)
        news_issue = _primary_issue(recent_news)
        return _simple_tone_conclusion(news_tone, news_issue, "新闻")

    recent_announcements = _recent_events(announcement_events, days=2) or announcement_events
    if recent_announcements:
        ann_tone = _sentiment_tone(recent_announcements)
        ann_issue = _primary_issue(recent_announcements)
        return _simple_tone_conclusion(ann_tone, ann_issue, "公告")

    if national_team_events:
        national_tone = _sentiment_tone(_recent_events(national_team_events, days=2) or national_team_events)
        if national_tone == "偏多":
            return "国家队相关线索偏多，说明大资金态度相对积极。"
        if national_tone == "偏空":
            return "国家队相关线索偏空，说明大资金态度偏谨慎。"
        return "国家队相关线索中性，暂未形成明确方向。"

    return "近两天消息面中性，暂未抓到足够有效的板块催化。"


def build_message_insight_text(
    announcement_events: List[Dict[str, Any]],
    news_events: List[Dict[str, Any]],
    theme_events: List[Dict[str, Any]],
    national_team_events: List[Dict[str, Any]],
) -> str:
    signal_text = build_message_signal_text(
        announcement_events=announcement_events,
        news_events=news_events,
        theme_events=theme_events,
        national_team_events=national_team_events,
    )
    parts = [signal_text]
    recent_news = _recent_events(news_events, days=2) or news_events
    recent_theme = _recent_events(theme_events, days=2) or theme_events
    if recent_news:
        parts.append(_channel_takeaway(recent_news[:3], "新闻"))
    if recent_theme:
        parts.append(_channel_takeaway(recent_theme[:3], "板块"))
    return " ".join(parts)


def _search_news_events(
    keywords: List[str],
    filter_terms: List[str],
    page_size: int = 5,
    extra_required_terms: Optional[List[str]] = None,
    channel: str = "新闻",
) -> Dict[str, Any]:
    collected: List[Dict[str, str]] = []
    seen_urls = set()
    total_delta = 0.0
    required_terms = [item for item in (extra_required_terms or []) if item]

    for keyword in keywords:
        query_payload = {
            "uid": "",
            "keyword": keyword,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "ALL",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": page_size,
                    "preTag": "<em>",
                    "postTag": "</em>",
                }
            },
        }
        url = "https://search-api-web.eastmoney.com/search/jsonp?" + urlencode(
            {"cb": "jQueryNews", "param": json.dumps(query_payload, ensure_ascii=False)}
        )
        try:
            response_text = _fetch_text(url, "https://so.eastmoney.com/")
            response_json = _parse_jsonp(response_text)
        except Exception:
            continue

        rows = ((response_json or {}).get("result") or {}).get("cmsArticleWebOld") or []
        for row in rows:
            title = _strip_tags(row.get("title", ""))
            content = _strip_tags(row.get("content", ""))
            article_url = row.get("url", "").strip()
            haystack = f"{title} {content}"
            if not title or not article_url or article_url in seen_urls:
                continue
            if filter_terms and not any(term in haystack for term in filter_terms):
                continue
            if required_terms and not any(term in haystack for term in required_terms):
                continue
            sentiment = _classify_news(title, content)
            seen_urls.add(article_url)
            total_delta += sentiment["delta"]
            collected.append(
                {
                    "title": title,
                    "meta": f"{sentiment['label']} | {row.get('mediaName', '东方财富')} | {row.get('date', '')}",
                    "published_at": row.get("date", ""),
                    "sentiment": sentiment["label"],
                    "channel": channel,
                    "source": row.get("mediaName", "东方财富"),
                    "url": article_url,
                }
            )
            if len(collected) >= page_size:
                break
        if len(collected) >= page_size:
            break

    if not collected:
        return {"events": [], "score_delta": 0.0, "reason_text": "暂未抓取到相关新闻。"}

    collected.sort(key=lambda item: item.get("published_at", ""), reverse=True)
    latest_date = collected[0]["published_at"]
    reason_text = f"已抓取到 {len(collected)} 条相关新闻，最新资讯时间为 {latest_date}。"
    return {"events": collected, "score_delta": total_delta / max(len(collected), 1), "reason_text": reason_text}


def fetch_recent_announcements(code: str, page_size: int = 5) -> Dict[str, Any]:
    url = f"https://api.fund.eastmoney.com/f10/JJGG?fundcode={code}&pageIndex=1&pageSize={page_size}&type=0"
    try:
        payload = _fetch_json(url)
    except Exception:
        return {"events": [], "score_delta": 0.0, "reason_text": "暂未成功抓取到最新公告。"}

    rows = payload.get("Data") or []
    events: List[Dict[str, str]] = []
    total_delta = 0.0

    for row in rows:
        title = row.get("TITLE", "").strip()
        publish_desc = row.get("PUBLISHDATEDesc", "")
        category = row.get("NEWCATEGORY", "")
        sentiment = _classify_announcement(title)
        total_delta += sentiment["delta"]
        events.append(
            {
                "title": title,
                "meta": f"{sentiment['label']} | 公告分类 {category} | {publish_desc}",
                "published_at": publish_desc,
                "sentiment": sentiment["label"],
                "channel": "公告",
                "source": "东方财富F10公告",
            }
        )

    if not events:
        return {"events": [], "score_delta": 0.0, "reason_text": "最近暂无公告可用。"}

    latest_date = events[0]["published_at"]
    reason_text = f"近期开出 {len(events)} 条真实公告，最新披露时间为 {latest_date}。"
    return {"events": events, "score_delta": total_delta / max(len(events), 1), "reason_text": reason_text}


def fetch_recent_news(fund_name: str, code: str, theme: str = "", company: str = "", page_size: int = 5) -> Dict[str, Any]:
    keywords = _news_keyword_candidates(fund_name, code, theme, company)
    normalized_name = _normalize_fund_name(fund_name)
    return _search_news_events(
        keywords=keywords,
        filter_terms=[fund_name, normalized_name],
        page_size=page_size,
        channel="新闻",
    )


def fetch_theme_news(fund_name: str, theme: str = "", page_size: int = 3) -> Dict[str, Any]:
    topic_terms = _topic_candidates(fund_name, theme)
    if not topic_terms:
        return {"events": [], "score_delta": 0.0, "reason_text": "未提取到有效板块关键词。"}
    return _search_news_events(
        keywords=topic_terms,
        filter_terms=topic_terms,
        page_size=page_size,
        channel="板块",
    )


def fetch_national_team_news(fund_name: str, theme: str = "", page_size: int = 3) -> Dict[str, Any]:
    topic_terms = _topic_candidates(fund_name, theme)
    national_terms = ["中央汇金", "国家队", "证金", "社保基金", "汇金", "险资"]
    if not topic_terms:
        topic_terms = [_normalize_fund_name(fund_name)]
    keywords = [f"{national_terms[0]} {topic_terms[0]}"]
    for term in national_terms[1:3]:
        keywords.append(f"{term} {topic_terms[0]}")
    snapshot = _search_news_events(
        keywords=keywords,
        filter_terms=topic_terms,
        page_size=page_size,
        extra_required_terms=national_terms,
        channel="国家队",
    )
    if snapshot["events"]:
        snapshot["score_delta"] = snapshot["score_delta"] * 1.2
    return snapshot


def _mix_dual_channel_events(
    announcement_events: List[Dict[str, Any]], news_events: List[Dict[str, Any]], limit: int = 8
) -> List[Dict[str, Any]]:
    announcement_sorted = sorted(announcement_events, key=_event_sort_key, reverse=True)
    news_sorted = sorted(news_events, key=_event_sort_key, reverse=True)

    if not announcement_sorted:
        return news_sorted[:limit]
    if not news_sorted:
        return announcement_sorted[:limit]

    mixed: List[Dict[str, Any]] = []
    ann_index = 0
    news_index = 0
    pick_news = _event_sort_key(news_sorted[0]) > _event_sort_key(announcement_sorted[0])

    while len(mixed) < limit and (ann_index < len(announcement_sorted) or news_index < len(news_sorted)):
        if pick_news and news_index < len(news_sorted):
            mixed.append(news_sorted[news_index])
            news_index += 1
        elif not pick_news and ann_index < len(announcement_sorted):
            mixed.append(announcement_sorted[ann_index])
            ann_index += 1
        elif news_index < len(news_sorted):
            mixed.append(news_sorted[news_index])
            news_index += 1
        elif ann_index < len(announcement_sorted):
            mixed.append(announcement_sorted[ann_index])
            ann_index += 1
        pick_news = not pick_news

    return mixed[:limit]


def fetch_message_snapshot(fund_name: str, code: str, theme: str = "", company: str = "") -> Dict[str, Any]:
    announcement_snapshot = fetch_recent_announcements(code, page_size=5)
    news_snapshot = fetch_recent_news(fund_name, code, theme=theme, company=company, page_size=5)
    theme_snapshot = fetch_theme_news(fund_name, theme=theme, page_size=3)
    national_team_snapshot = fetch_national_team_news(fund_name, theme=theme, page_size=3)
    announcement_events = announcement_snapshot.get("events", [])
    news_events = news_snapshot.get("events", [])
    theme_events = theme_snapshot.get("events", [])
    national_team_events = national_team_snapshot.get("events", [])
    events = _mix_dual_channel_events(
        announcement_events + theme_events,
        news_events + national_team_events,
        limit=10,
    )
    score_delta = (
        float(announcement_snapshot.get("score_delta", 0.0)) * 0.9
        + float(news_snapshot.get("score_delta", 0.0))
        + float(theme_snapshot.get("score_delta", 0.0)) * 0.8
        + float(national_team_snapshot.get("score_delta", 0.0)) * 1.1
    )
    reason_text = build_message_insight_text(
        announcement_events=announcement_events,
        news_events=news_events,
        theme_events=theme_events,
        national_team_events=national_team_events,
    )
    return {
        "announcement_events": announcement_events,
        "news_events": news_events,
        "theme_events": theme_events,
        "national_team_events": national_team_events,
        "all_events": announcement_events + news_events + theme_events + national_team_events,
        "events": events,
        "score_delta": score_delta,
        "reason_text": reason_text,
        "signal_text": build_message_signal_text(
            announcement_events=announcement_events,
            news_events=news_events,
            theme_events=theme_events,
            national_team_events=national_team_events,
        ),
    }


def build_message_reason_text(events: List[Dict[str, str]]) -> str:
    if not events:
        return "最近未抓取到公告或新闻，消息面采用较弱权重处理。"
    latest = events[0]
    channel = latest.get("channel", "消息")
    issue = _issue_from_title(latest.get("title", ""), channel)
    tone = _sentiment_tone(events)
    return f"最近{channel}主要反映“{issue}”，整体偏{tone}，最新事件为《{latest['title']}》。"


def build_event_cards(events: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [
        {
            "title": item["title"],
            "meta": item["meta"],
            "channel": item.get("channel"),
            "source": item.get("source"),
            "url": item.get("url"),
            "published_at": item.get("published_at"),
        }
        for item in events[:5]
    ]


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
