import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import akshare as ak
import pandas as pd


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
FUND_GZ_URL = "https://fundgz.1234567.com.cn/js/{code}.js"
FUND_HOT_URL = "https://fund.eastmoney.com/fundhot8.html"
FUND_RANKING_URL = (
    "https://fund.eastmoney.com/data/fundranking.html"
    "?ft=all&rs=&gs=0&sc=rzdf&st=desc&sd={start_date}&ed={end_date}&qdii=042|&tabSubtype=,,,,,&pi=1&pn=120&dx=1"
)


@dataclass
class ExternalFundPayload:
    code: str
    name: str
    fund_type: str
    risk_level: str
    company: str
    latest_nav: float
    estimated_nav: float
    estimated_change_rate: float
    theme: str
    metrics: Dict[str, Any]


@dataclass
class HotFundCandidate:
    code: str
    name: str
    fund_type: str
    hot_reason: str


@dataclass
class RankedFundCandidate:
    code: str
    name: str
    board: str
    daily_change: float


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Referer": "https://fund.eastmoney.com/"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="ignore")


def _parse_jsonp_payload(text: str) -> Dict[str, Any]:
    start = text.find("(")
    end = text.rfind(")")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start + 1 : end])
    except json.JSONDecodeError:
        return {}


def _extract_js_value(text: str, variable_name: str) -> Any:
    match = re.search(rf"var\s+{re.escape(variable_name)}\s*=\s*(.*?);", text, re.S)
    if not match:
        return None
    raw_value = match.group(1).strip()
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value.strip('"').strip("'")


def _clean_html_text(raw: str) -> str:
    return html.unescape(re.sub(r"<.*?>", "", raw)).replace("\xa0", " ").strip()


def _extract_html_group(pattern: str, text: str, default: str = "") -> str:
    match = re.search(pattern, text, re.S)
    if not match:
        return default
    return _clean_html_text(match.group(1))


def _parse_mmdd_date(text: str) -> str:
    match = re.search(r"(\d{2})-(\d{2})", text or "")
    if not match:
        return ""
    month = int(match.group(1))
    day = int(match.group(2))
    year = datetime.now().year
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _extract_official_nav_from_detail(html_text: str) -> Dict[str, Any]:
    date_match = re.search(r'class="fix_date">\((\d{2}-\d{2})\)', html_text or "", re.I)
    nav_match = re.search(r'class="fix_dwjz[^"]*">\s*([0-9.]+)\s*<', html_text or "", re.I)
    rate_match = re.search(r'class="fix_zzl[^"]*">\s*([+-]?[0-9.]+)%\s*<', html_text or "", re.I)
    if not (date_match and nav_match):
        return {}
    official_date = _parse_mmdd_date(date_match.group(1))
    if not official_date:
        return {}
    return {
        "date": official_date,
        "nav": _safe_float(nav_match.group(1), 0.0),
        "rate": _safe_float(rate_match.group(1), 0.0) if rate_match else 0.0,
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _compact_nav_series(rows: Any, limit: int = 240) -> List[Dict[str, float]]:
    series: List[Dict[str, float]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ts = int(_safe_float(row.get("x"), 0.0))
        nav = _safe_float(row.get("y"), 0.0)
        change = _safe_float(row.get("equityReturn"), 0.0)
        if ts <= 0 or nav <= 0:
            continue
        series.append({"ts": ts, "nav": nav, "change": change})
    return series[-limit:]


def _compact_position_series(rows: Any, limit: int = 120) -> List[Dict[str, float]]:
    series: List[Dict[str, float]] = []
    for row in rows or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        ts = int(_safe_float(row[0], 0.0))
        position = _safe_float(row[1], 0.0)
        if ts <= 0:
            continue
        series.append({"ts": ts, "position": position})
    return series[-limit:]


def _date_from_ts(ts: Any) -> str:
    try:
        value = int(float(ts))
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    if value > 10**12:
        value = value / 1000
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d")


def _normalize_risk_level(raw_risk: str) -> str:
    if not raw_risk:
        return "未知"
    return raw_risk.replace("风险", "").strip()


def _share_class_priority(name: str) -> int:
    text = (name or "").strip()
    for suffix, priority in (("C", 0), ("A", 1), ("E", 2), ("I", 3)):
        if text.endswith(suffix):
            return priority
    return 4


def _fund_name_base(name: str) -> str:
    text = re.sub(r"\s+", "", name or "")
    for suffix in ("人民币C", "人民币A", "人民币E", "人民币I", "C", "A", "E", "I"):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def _is_equity_hot_type(fund_type: str) -> bool:
    text = fund_type or ""
    blocked_tokens = ("债券", "货币", "理财", "短债", "中短债", "纯债")
    if any(token in text for token in blocked_tokens):
        return False
    return any(token in text for token in ("股票", "混合", "指数", "QDII", "FOF"))


def _classify_fund_board(name: str) -> str:
    text = (name or "").lower()
    keyword_map = [
        (("半导体", "芯片", "集成电路", "科创芯片"), "半导体"),
        (("人工智能", "ai", "算力", "cpo", "通信", "光模块", "数字", "科技", "信息"), "科技成长"),
        (("新能源", "电池", "光伏", "储能", "锂", "风电"), "新能源"),
        (("医药", "医疗", "创新药", "生物", "健康"), "医药"),
        (("消费", "白酒", "食品", "家电", "品牌"), "消费"),
        (("军工", "国防", "卫星", "航天", "装备"), "军工"),
        (("机器人", "智能汽车", "汽车", "制造"), "高端制造"),
        (("有色", "黄金", "资源", "煤炭", "金属"), "资源周期"),
        (("银行", "证券", "保险", "红利", "价值", "央企"), "红利金融"),
        (("港股", "恒生", "纳斯达克", "标普", "全球", "海外", "qdii"), "海外市场"),
        (("中证", "沪深", "上证", "深证", "a500", "创业板", "科创板", "300", "500", "1000", "etf"), "宽基指数"),
    ]
    for keywords, board in keyword_map:
        if any(keyword in text for keyword in keywords):
            return board
    return "综合主题"


def _extract_hot_section(html_text: str, marker: str) -> str:
    marker_index = html_text.find(marker)
    if marker_index == -1:
        return ""
    tail = html_text[marker_index:]
    table_match = re.search(r"<table.*?</table>", tail, re.S | re.I)
    if not table_match:
        return ""
    return table_match.group(0)


def _parse_hot_rows(section_html: str, default_type: str, hot_reason: str) -> List[HotFundCandidate]:
    rows: List[HotFundCandidate] = []
    for row_html in re.findall(r"<tr.*?</tr>", section_html or "", re.S | re.I):
        fund_match = re.search(r'<a[^>]+href="https?://fund\.eastmoney\.com/(\d{6})\.html"[^>]*>([^<]+)</a>', row_html, re.I)
        if not fund_match:
            continue
        code = fund_match.group(1)
        name = _clean_html_text(fund_match.group(2))
        cell_values = [
            _clean_html_text(item)
            for item in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S | re.I)
        ]
        fund_type = default_type
        for value in cell_values:
            if any(token in value for token in ("股票", "混合", "指数", "QDII", "债券", "货币", "FOF")):
                fund_type = value
                break
        if not _is_equity_hot_type(fund_type):
            continue
        rows.append(
            HotFundCandidate(
                code=code,
                name=name,
                fund_type=fund_type,
                hot_reason=hot_reason,
            )
        )
    return rows


def _parse_percent(text: str) -> Optional[float]:
    match = re.search(r"([+-]?\d+(?:\.\d+)?)%", text or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_rank_rows(section_html: str) -> List[RankedFundCandidate]:
    rows: List[RankedFundCandidate] = []
    for row_html in re.findall(r"<tr.*?</tr>", section_html or "", re.S | re.I):
        fund_match = re.search(r'<a[^>]+href="https?://fund\.eastmoney\.com/(\d{6})\.html"[^>]*>([^<]+)</a>', row_html, re.I)
        if not fund_match:
            continue
        code = fund_match.group(1)
        name = _clean_html_text(fund_match.group(2))
        if not name:
            continue
        cell_values = [
            _clean_html_text(item)
            for item in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S | re.I)
        ]
        percent_values = [_parse_percent(value) for value in cell_values]
        percent_values = [value for value in percent_values if value is not None]
        if not percent_values:
            continue
        daily_change = float(percent_values[0])
        rows.append(
            RankedFundCandidate(
                code=code,
                name=name,
                board=_classify_fund_board(name),
                daily_change=daily_change,
            )
        )
    return rows


def fetch_hot_fund_candidates(limit: int = 12) -> List[HotFundCandidate]:
    html_text = _fetch_text(FUND_HOT_URL)
    monthly_html = _extract_hot_section(html_text, "月销量总榜")
    stock_html = _extract_hot_section(html_text, "股票型收益极佳的掘金利器")
    mixed_html = _extract_hot_section(html_text, "混合型收益可观，攻守兼备，风险可控")

    rows = [
        *_parse_hot_rows(monthly_html, "热销基金", "东财热销"),
        *_parse_hot_rows(stock_html, "股票型", "东财热门股票型"),
        *_parse_hot_rows(mixed_html, "混合型", "东财热门混合型"),
    ]
    deduped: Dict[str, HotFundCandidate] = {}
    for item in rows:
        base_name = _fund_name_base(item.name)
        existed = deduped.get(base_name)
        if not existed or _share_class_priority(item.name) < _share_class_priority(existed.name):
            deduped[base_name] = item
    return list(deduped.values())[:limit]


def fetch_top_gainer_fund_candidates(limit: int = 24) -> List[RankedFundCandidate]:
    rows: List[RankedFundCandidate] = []
    daily_df = ak.fund_open_fund_daily_em()
    if daily_df.empty:
        return rows
    ranked_df = daily_df.copy()
    ranked_df["日增长率"] = ranked_df["日增长率"].replace("", None)
    ranked_df["日增长率"] = ranked_df["日增长率"].astype(str).str.replace("%", "", regex=False)
    ranked_df["日增长率"] = pd.to_numeric(ranked_df["日增长率"], errors="coerce")
    ranked_df = ranked_df.dropna(subset=["日增长率"]).sort_values(by="日增长率", ascending=False)
    for _, row in ranked_df.iterrows():
        fund_code = str(row.get("基金代码", "")).zfill(6)
        fund_name = str(row.get("基金简称", "")).strip()
        if not fund_code or not fund_name:
            continue
        rows.append(
            RankedFundCandidate(
                code=fund_code,
                name=fund_name,
                board=_classify_fund_board(fund_name),
                daily_change=float(row.get("日增长率", 0.0) or 0.0),
            )
        )
    deduped: Dict[str, RankedFundCandidate] = {}
    for item in rows:
        base_name = _fund_name_base(item.name)
        existed = deduped.get(base_name)
        if not existed or _share_class_priority(item.name) < _share_class_priority(existed.name):
            deduped[base_name] = item
    ordered = list(deduped.values())
    diversified: List[RankedFundCandidate] = []
    used_boards = set()
    for item in ordered:
        if item.board in used_boards:
            continue
        diversified.append(item)
        used_boards.add(item.board)
        if len(diversified) >= limit:
            return diversified
    for item in ordered:
        if item in diversified:
            continue
        diversified.append(item)
        if len(diversified) >= limit:
            break
    return diversified


def _infer_theme(fund_type: str, metrics: Dict[str, Any]) -> str:
    manager_name = metrics.get("manager_name", "")
    if "指数" in fund_type:
        return "指数基金"
    if "债" in fund_type:
        return "固收基金"
    if "货币" in fund_type:
        return "现金管理"
    if manager_name:
        return f"{manager_name} 管理"
    return "公募基金"


def fetch_fund_profile(code: str) -> ExternalFundPayload:
    pingzhong_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    detail_url = f"https://fund.eastmoney.com/{code}.html"
    fund_gz_url = FUND_GZ_URL.format(code=code)

    try:
        js_text = _fetch_text(pingzhong_url)
        html_text = _fetch_text(detail_url)
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError(f"未查询到基金代码 {code}，请确认是有效公募基金代码") from exc
        raise ValueError(f"外部基金数据源请求失败: HTTP {exc.code}") from exc
    except Exception as exc:
        raise ValueError("外部基金数据源暂时不可用，请稍后重试") from exc

    name = _extract_js_value(js_text, "fS_name") or code
    js_code = _extract_js_value(js_text, "fS_code") or code
    net_worth_trend = _extract_js_value(js_text, "Data_netWorthTrend") or []
    latest_point = net_worth_trend[-1] if net_worth_trend else {}
    previous_point = net_worth_trend[-2] if len(net_worth_trend) >= 2 else {}

    one_month_return = _safe_float(_extract_js_value(js_text, "syl_1y"))
    three_month_return = _safe_float(_extract_js_value(js_text, "syl_3y"))
    six_month_return = _safe_float(_extract_js_value(js_text, "syl_6y"))
    one_year_return = _safe_float(_extract_js_value(js_text, "syl_1n"))
    manager_info = _extract_js_value(js_text, "Data_currentFundManager") or []
    scale_info = _extract_js_value(js_text, "Data_fluctuationScale") or {}
    position_series = _extract_js_value(js_text, "Data_fundSharesPositions") or []
    stock_codes_new = _extract_js_value(js_text, "stockCodesNew") or []

    type_and_risk = _extract_html_group(
        r"<td>类型：<a[^>]*>(.*?)</a>&nbsp;&nbsp;\|&nbsp;&nbsp;(.*?)</td>",
        html_text,
    )
    fund_type = _extract_html_group(r"<td>类型：<a[^>]*>(.*?)</a>", html_text, "未知类型")
    risk_level = _extract_html_group(r"&nbsp;&nbsp;\|&nbsp;&nbsp;([^<]*?)</td>", html_text, "未知风险")
    company = _extract_html_group(r"管 理 人</span>：<a[^>]*>(.*?)</a>", html_text, "")
    scale_text = _extract_html_group(r">规模</a>：([^<]*?)</td>", html_text, "")

    manager_name = ""
    manager_star = 0.0
    if manager_info:
        manager_name = manager_info[0].get("name", "")
        manager_star = _safe_float(manager_info[0].get("star"))

    scale_mom = 0.0
    series = scale_info.get("series") or []
    if series:
        scale_mom_raw = series[-1].get("mom", "0")
        scale_mom = _safe_float(str(scale_mom_raw).replace("%", ""))

    latest_nav = _safe_float(latest_point.get("y"), 0.0)
    previous_nav = _safe_float(previous_point.get("y"), 0.0)
    estimated_change_rate = _safe_float(latest_point.get("equityReturn"), 0.0)
    estimated_nav = latest_nav
    latest_nav_date = _date_from_ts(latest_point.get("x"))
    try:
        gz_payload = _parse_jsonp_payload(_fetch_text(fund_gz_url))
        estimated_nav = _safe_float(gz_payload.get("gsz"), estimated_nav)
        estimated_change_rate = _safe_float(gz_payload.get("gszzl"), estimated_change_rate)
        latest_nav = _safe_float(gz_payload.get("dwjz"), latest_nav)
        latest_nav_date = str(gz_payload.get("jzrq") or latest_nav_date or "").strip()
    except Exception:
        pass
    latest_point_date = _date_from_ts(latest_point.get("x"))
    official_from_detail = _extract_official_nav_from_detail(html_text)
    if official_from_detail:
        detail_date = str(official_from_detail.get("date") or "").strip()
        detail_nav = _safe_float(official_from_detail.get("nav"), 0.0)
        detail_rate = _safe_float(official_from_detail.get("rate"), 0.0)
        if detail_date and detail_nav > 0 and detail_date >= (latest_nav_date or latest_point_date):
            previous_nav = latest_nav if detail_date > (latest_nav_date or latest_point_date) else previous_nav
            latest_nav = detail_nav
            latest_nav_date = detail_date
            if abs(detail_rate) > 0.0001:
                official_daily_rate = detail_rate
            else:
                official_daily_rate = round(((latest_nav / previous_nav) - 1) * 100, 4) if latest_nav > 0 and previous_nav > 0 else 0.0
        else:
            official_daily_rate = round(((latest_nav / previous_nav) - 1) * 100, 4) if latest_nav > 0 and previous_nav > 0 else 0.0
    else:
        official_daily_rate = round(((latest_nav / previous_nav) - 1) * 100, 4) if latest_nav > 0 and previous_nav > 0 else 0.0

    if (not name or name == code) and fund_type == "未知类型" and latest_nav <= 0:
        raise ValueError(f"未查询到基金代码 {code}，请确认是有效公募基金代码")

    metrics = {
        "one_month_return": one_month_return,
        "three_month_return": three_month_return,
        "six_month_return": six_month_return,
        "one_year_return": one_year_return,
        "scale_mom": scale_mom,
        "manager_name": manager_name,
        "manager_star": manager_star,
        "scale_text": scale_text,
        "type_and_risk": type_and_risk,
        "nav_series": _compact_nav_series(net_worth_trend),
        "position_series": _compact_position_series(position_series),
        "stock_codes": [str(code) for code in stock_codes_new if code],
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "latest_nav_date": latest_nav_date,
        "previous_nav": previous_nav,
        "official_daily_rate": official_daily_rate,
    }

    return ExternalFundPayload(
        code=str(js_code),
        name=name,
        fund_type=fund_type,
        risk_level=_normalize_risk_level(risk_level),
        company=company,
        latest_nav=latest_nav,
        estimated_nav=estimated_nav,
        estimated_change_rate=estimated_change_rate,
        theme=_infer_theme(fund_type, metrics),
        metrics=metrics,
    )
