import io
import json
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from rapidocr_onnxruntime import RapidOCR
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ocr import OCRExtractionItem, OCRJob
from app.models.portfolio import PortfolioHolding
from app.schemas.ocr import OCRItemUpdateRequest, OCRJobResponse, OCRItemResponse, OCRSimulateRequest
from app.services.external_fund_service import fetch_fund_profile
from app.services.seed_data import MOCK_OCR

UPLOAD_DIR = Path("backend/uploads/ocr")
USER_AGENT = "Mozilla/5.0"
FUND_CATALOG_URL = "https://fund.eastmoney.com/js/fundcode_search.js"
DEBUG_ENV_PATH = Path(".dbg/ocr-profit-missing.env")
IGNORE_TEXT_SNIPPETS = (
    "账户汇总",
    "支付宝",
    "账户资产",
    "场内",
    "基金",
    "今日收益",
    "关联板块",
    "持有收益",
    "新增持有",
    "批量加减仓",
    "上证指数",
    "持有",
    "自选",
    "行情",
    "资讯",
    "会员",
    "我的",
)


@dataclass
class OCRTextBlock:
    text: str
    score: float
    left: float
    top: float
    right: float
    bottom: float

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class OCRCandidate:
    fund_code: str
    fund_name: str
    shares: float
    amount: float
    profit: float
    confidence: str


# #region debug-point A:ocr-report
def _debug_report(hypothesis_id: str, location: str, msg: str, data: Optional[Dict[str, object]] = None) -> None:
    _url = "http://127.0.0.1:7777/event"
    _session = "ocr-profit-missing"
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


def _build_ocr_response(job: OCRJob, items: List[OCRExtractionItem]) -> OCRJobResponse:
    return OCRJobResponse(
        job_id=job.id,
        status=job.status,
        items=[
            OCRItemResponse(
                id=item.id,
                fund_code=item.fund_code,
                fund_name=item.fund_name,
                shares=item.shares,
                amount=item.amount,
                profit=item.profit,
                confidence=item.confidence,
            )
            for item in items
        ],
    )


def _persist_ocr_job(db: Session, filename: str, extracted_items: List[OCRCandidate]) -> OCRJobResponse:
    job = OCRJob(
        filename=filename,
        status="completed",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    db.add(job)
    db.flush()

    items: List[OCRExtractionItem] = []
    for row in extracted_items:
        item = OCRExtractionItem(
            job_id=job.id,
            fund_code=row.fund_code,
            fund_name=row.fund_name,
            shares=row.shares,
            amount=row.amount,
            profit=row.profit,
            confidence=row.confidence,
        )
        db.add(item)
        items.append(item)
    db.commit()

    return _build_ocr_response(job, items)


def _create_mock_ocr_job(db: Session, filename: str) -> OCRJobResponse:
    mock_items = [
        OCRCandidate(
            fund_code=row["fund_code"],
            fund_name=row["fund_name"],
            shares=row["shares"],
            amount=row["amount"],
            profit=row.get("profit", 0.0),
            confidence=row["confidence"],
        )
        for row in MOCK_OCR["items"]
    ]
    return _persist_ocr_job(db, filename, mock_items)


@lru_cache(maxsize=1)
def _ocr_engine() -> RapidOCR:
    return RapidOCR()


@lru_cache(maxsize=1)
def _fund_catalog() -> List[Tuple[str, str]]:
    request = Request(FUND_CATALOG_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8", errors="ignore").lstrip("\ufeff")
    start = payload.find("[")
    end = payload.rfind("]")
    rows = json.loads(payload[start : end + 1])
    return [(row[0], row[2]) for row in rows if len(row) >= 3]


def _clean_text(text: str) -> str:
    return (
        (text or "")
        .replace("|", "")
        .replace("｜", "")
        .replace("（", "(")
        .replace("）", ")")
        .replace("…", "")
        .replace("...", "")
        .replace(" ", "")
        .strip()
    )


def _normalize_fund_name(name: str) -> str:
    cleaned = _clean_text(name)
    cleaned = cleaned.replace("(", "").replace(")", "")
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", cleaned)
    cleaned = re.sub(r"[A-CEHIOR]$", "", cleaned)
    return cleaned


def _fund_name_base(name: str) -> str:
    cleaned = _clean_text(name)
    cleaned = cleaned.replace("(LOF)", "").replace("LOF", "")
    cleaned = cleaned.replace("联接", "").replace("发起式", "")
    cleaned = re.sub(r"[()（）]", "", cleaned)
    cleaned = re.sub(r"[A-CEHIOR]$", "", cleaned)
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", cleaned)
    return cleaned


def _share_class_priority(name: str) -> int:
    cleaned = _clean_text(name).upper()
    if cleaned.endswith("(LOF)C") or cleaned.endswith("LOFC") or cleaned.endswith("C"):
        return 3
    if cleaned.endswith("(LOF)A") or cleaned.endswith("LOFA") or cleaned.endswith("A"):
        return 2
    return 1


def _preprocess_image(content: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(content)).convert("L")
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Sharpness(image).enhance(2.2)
    if image.width < 1000:
        scale = 1000 / float(image.width)
        image = image.resize((1000, int(image.height * scale)))
    return np.array(image)


def _to_text_blocks(raw_result: Optional[List[List[object]]]) -> List[OCRTextBlock]:
    blocks: List[OCRTextBlock] = []
    for item in raw_result or []:
        if len(item) < 3:
            continue
        box = item[0]
        text = _clean_text(str(item[1]))
        score = float(item[2] or 0)
        if not text:
            continue
        xs = [point[0] for point in box]
        ys = [point[1] for point in box]
        blocks.append(
            OCRTextBlock(
                text=text,
                score=score,
                left=min(xs),
                top=min(ys),
                right=max(xs),
                bottom=max(ys),
            )
        )
    return sorted(blocks, key=lambda item: (item.center_y, item.left))


def _is_noise_text(text: str) -> bool:
    if not text:
        return True
    if any(token in text for token in IGNORE_TEXT_SNIPPETS):
        return True
    if re.fullmatch(r"[+\-]?\d+(\.\d+)?%", text):
        return True
    if re.fullmatch(r"[+\-]?\d+(\.\d+)?", text):
        return True
    return False


def _looks_like_fund_name(block: OCRTextBlock, image_width: int) -> bool:
    text = block.text
    if _is_noise_text(text):
        return False
    if block.left > image_width * 0.45:
        return False
    if len(re.findall(r"[\u4e00-\u9fff]", text)) < 4:
        return False
    if "收益" in text or "持仓" in text:
        return False
    return True


def _parse_amount(text: str) -> Optional[float]:
    match = re.search(r"[¥￥]?\s*([0-9][0-9,]*\.[0-9]{2})", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_signed_amount(text: str) -> Optional[float]:
    normalized = (text or "").replace(",", "").replace("，", "").replace(" ", "")
    match = re.search(r"([+\-]?\d+(?:\.\d{1,2})?)", normalized)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _is_percent_text(text: str) -> bool:
    return bool(re.fullmatch(r"[+\-]?\d+(?:\.\d+)?%", (text or "").strip()))


def _find_row_amount(name_block: OCRTextBlock, next_name_top: float, blocks: List[OCRTextBlock], image_width: int) -> float:
    candidates: List[Tuple[float, float]] = []
    for block in blocks:
        if block.left > image_width * 0.42:
            continue
        if block.bottom < name_block.top - 8:
            continue
        if block.top >= next_name_top - 8:
            continue
        amount = _parse_amount(block.text)
        if amount is None:
            continue
        priority = 0 if ("￥" in block.text or "¥" in block.text or "已更新" in block.text) else 1
        distance = (
            priority * 1000
            + max(0.0, name_block.center_y - block.center_y) * 3
            + abs(block.center_y - name_block.center_y)
            + abs(block.left - name_block.left) * 0.2
        )
        candidates.append((distance, amount))
    if not candidates:
        return 0.0
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _find_row_profit(name_block: OCRTextBlock, next_name_top: float, blocks: List[OCRTextBlock], image_width: int) -> float:
    candidates: List[Tuple[float, float]] = []
    for block in blocks:
        if block.left < image_width * 0.48:
            continue
        if block.bottom < name_block.top - 10:
            continue
        if block.top >= next_name_top - 8:
            continue
        if _is_percent_text(block.text):
            continue
        if any(token in block.text for token in ("净值", "估值", "代码", "份额")):
            continue
        profit = _parse_signed_amount(block.text)
        if profit is None:
            continue
        if abs(profit) > 999999:
            continue
        # 支付宝持仓页里，持有收益通常位于同一行靠右区域，很多时候 OCR 只会识别成纯数字。
        horizontal_bias = abs(block.left - image_width * 0.72) * 0.05
        vertical_bias = abs(block.center_y - name_block.center_y) * 0.9
        far_right_bonus = -min(block.left, image_width) * 0.01
        distance = vertical_bias + horizontal_bias + far_right_bonus
        candidates.append((distance, profit))
    if not candidates:
        return 0.0
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _find_nearby_code(name_block: OCRTextBlock, blocks: List[OCRTextBlock]) -> str:
    for block in blocks:
        if abs(block.center_y - name_block.center_y) > 25:
            continue
        match = re.search(r"\b(\d{6})\b", block.text)
        if match:
            return match.group(1)
    return ""


def _match_fund_name(raw_name: str) -> Optional[Tuple[str, str, float]]:
    normalized_raw = _normalize_fund_name(raw_name)
    base_raw = _fund_name_base(raw_name)
    if len(normalized_raw) < 2:
        return None

    best_match: Optional[Tuple[str, str, float, int]] = None
    for code, name in _fund_catalog():
        normalized_name = _normalize_fund_name(name)
        base_name = _fund_name_base(name)
        ratio = SequenceMatcher(None, normalized_raw, normalized_name).ratio()
        if normalized_name.startswith(normalized_raw) or normalized_raw.startswith(normalized_name):
            ratio = max(ratio, 0.92)
        elif normalized_raw in normalized_name:
            ratio = max(ratio, 0.85)
        class_priority = _share_class_priority(name)
        if base_raw and base_name == base_raw:
            ratio = max(ratio, 0.94 if class_priority >= 3 else 0.90)
        if normalized_raw == normalized_name:
            ratio = max(ratio, 0.98)
        candidate = (code, name, ratio, class_priority)
        if not best_match:
            best_match = candidate
            continue
        if ratio > best_match[2] + 1e-6:
            best_match = candidate
            continue
        if abs(ratio - best_match[2]) <= 0.015 and class_priority > best_match[3]:
            best_match = candidate

    if best_match and best_match[2] >= 0.60:
        return best_match[0], best_match[1], best_match[2]
    return None


def _recalculate_shares(fund_code: str, amount: float, manual_shares: Optional[float] = None) -> float:
    if manual_shares is not None and manual_shares > 0:
        return round(float(manual_shares), 2)
    payload = fetch_fund_profile(fund_code)
    nav = payload.estimated_nav or payload.latest_nav or 0.0
    if nav <= 0 or amount <= 0:
        return 0.0
    return round(amount / nav, 2)


def _confidence_label(ocr_score: float, match_score: float, has_amount: bool, inferred_shares: bool) -> str:
    composite = ocr_score * 0.45 + match_score * 0.40 + (0.10 if has_amount else 0) + (0.05 if not inferred_shares else 0)
    if composite >= 0.88:
        return "高"
    if composite >= 0.72:
        return "中"
    return "低"


def _extract_alipay_holdings(content: bytes) -> List[OCRCandidate]:
    image = _preprocess_image(content)
    raw_result, _ = _ocr_engine()(image)
    blocks = _to_text_blocks(raw_result)
    # #region debug-point A:ocr-blocks
    _debug_report("A", "ocr_service:_extract_alipay_holdings:blocks", "ocr blocks parsed", {"block_count": len(blocks), "image_width": int(image.shape[1]), "image_height": int(image.shape[0]), "sample_texts": [block.text for block in blocks[:12]]})
    # #endregion
    if not blocks:
        return []

    image_width = int(image.shape[1])
    name_blocks = [block for block in blocks if _looks_like_fund_name(block, image_width)]

    deduped_name_blocks: List[OCRTextBlock] = []
    last_y = -10_000.0
    for block in name_blocks:
        if abs(block.center_y - last_y) < 28:
            continue
        deduped_name_blocks.append(block)
        last_y = block.center_y
    # #region debug-point B:name-blocks
    _debug_report("B", "ocr_service:_extract_alipay_holdings:names", "candidate name blocks selected", {"name_block_count": len(name_blocks), "deduped_count": len(deduped_name_blocks), "names": [block.text for block in deduped_name_blocks[:10]]})
    # #endregion

    candidates: List[OCRCandidate] = []
    seen_codes = set()
    for index, block in enumerate(deduped_name_blocks):
        code = _find_nearby_code(block, blocks)
        matched_name = ""
        match_score = 0.0
        if code:
            try:
                payload = fetch_fund_profile(code)
                matched_name = payload.name
                match_score = 1.0
            except ValueError:
                code = ""

        if not code:
            matched = _match_fund_name(block.text)
            if not matched:
                continue
            code, matched_name, match_score = matched

        if code in seen_codes:
            continue

        next_name_top = (
            deduped_name_blocks[index + 1].top
            if index + 1 < len(deduped_name_blocks)
            else float(image.shape[0]) + 1
        )
        amount = _find_row_amount(block, next_name_top, blocks, image_width)
        profit = _find_row_profit(block, next_name_top, blocks, image_width)
        # #region debug-point C:row-values
        _debug_report("C", "ocr_service:_extract_alipay_holdings:row", "row values extracted", {"raw_name": block.text, "matched_code": code, "matched_name": matched_name, "amount": amount, "profit": profit, "top": round(block.top, 2), "left": round(block.left, 2), "next_name_top": round(next_name_top, 2)})
        # #endregion
        try:
            payload = fetch_fund_profile(code)
        except ValueError:
            continue

        nav = payload.estimated_nav or payload.latest_nav or 0.0
        inferred_shares = nav > 0 and amount > 0
        shares = round(amount / nav, 2) if inferred_shares else 0.0
        confidence = _confidence_label(block.score, match_score, amount > 0, inferred_shares)

        if shares <= 0 and amount <= 0:
            continue

        candidates.append(
            OCRCandidate(
                fund_code=code,
                fund_name=matched_name or payload.name,
                shares=shares,
                amount=amount,
                profit=profit,
                confidence=confidence,
            )
        )
        seen_codes.add(code)

    # #region debug-point D:ocr-candidates
    _debug_report("D", "ocr_service:_extract_alipay_holdings:done", "ocr candidates built", {"candidate_count": len(candidates), "candidates": [{"fund_code": item.fund_code, "fund_name": item.fund_name, "amount": item.amount, "profit": item.profit, "shares": item.shares} for item in candidates[:10]]})
    # #endregion
    return candidates


def simulate_ocr(db: Session, payload: OCRSimulateRequest) -> OCRJobResponse:
    return _create_mock_ocr_job(db, payload.filename)


def upload_ocr_image(db: Session, filename: str, content: bytes) -> OCRJobResponse:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("仅支持 png、jpg、jpeg、webp 图片")
    if len(content) == 0:
        raise ValueError("上传图片为空，请重新选择")
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("图片大小不能超过 10MB")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{Path(filename).name}"
    file_path = UPLOAD_DIR / stored_name
    file_path.write_bytes(content)
    # #region debug-point E:upload
    _debug_report("E", "ocr_service:upload_ocr_image:start", "ocr upload received", {"filename": filename, "stored_name": stored_name, "size": len(content)})
    # #endregion

    extracted_items = _extract_alipay_holdings(content)
    if not extracted_items:
        # #region debug-point E:upload-empty
        _debug_report("E", "ocr_service:upload_ocr_image:empty", "ocr extracted empty result", {"filename": filename, "stored_name": stored_name})
        # #endregion
        raise ValueError("未能从截图中识别出持仓基金，请上传更清晰的支付宝/基金持仓列表截图")

    # #region debug-point E:upload-success
    _debug_report("E", "ocr_service:upload_ocr_image:success", "ocr upload completed", {"filename": filename, "stored_name": stored_name, "item_count": len(extracted_items)})
    # #endregion
    return _persist_ocr_job(db, stored_name, extracted_items)


def get_ocr_job(db: Session, job_id: int) -> OCRJobResponse:
    job = db.get(OCRJob, job_id)
    if not job:
        raise ValueError(f"OCR 任务 {job_id} 不存在")
    items = db.scalars(select(OCRExtractionItem).where(OCRExtractionItem.job_id == job_id)).all()
    return OCRJobResponse(
        job_id=job.id,
        status=job.status,
        items=[OCRItemResponse.model_validate(item, from_attributes=True) for item in items],
    )


def update_ocr_item(db: Session, job_id: int, item_id: int, payload: OCRItemUpdateRequest) -> OCRJobResponse:
    job = db.get(OCRJob, job_id)
    if not job:
        raise ValueError(f"OCR 任务 {job_id} 不存在")
    item = db.get(OCRExtractionItem, item_id)
    if not item or item.job_id != job_id:
        raise ValueError(f"OCR 条目 {item_id} 不存在")
    code = (payload.fund_code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("基金代码必须为 6 位数字")
    amount = round(float(payload.amount or 0), 2)
    if amount <= 0:
        raise ValueError("识别金额必须大于 0")
    profit = round(float(payload.profit or 0), 2)
    fund_payload = fetch_fund_profile(code)
    item.fund_code = code
    item.fund_name = (payload.fund_name or "").strip() or fund_payload.name
    item.amount = amount
    item.profit = profit
    item.shares = _recalculate_shares(code, amount, payload.shares)
    db.commit()
    return get_ocr_job(db, job_id)


def confirm_ocr_to_portfolio(db: Session, job_id: int) -> Dict[str, int]:
    items = db.scalars(select(OCRExtractionItem).where(OCRExtractionItem.job_id == job_id)).all()
    created = 0
    for item in items:
        exists = db.scalar(select(PortfolioHolding).where(PortfolioHolding.fund_code == item.fund_code))
        if exists:
            exists.shares = round(exists.shares + item.shares, 2)
            exists.cost_amount = round(exists.cost_amount + item.amount - item.profit, 2)
            exists.source = "ocr"
        else:
            db.add(
                PortfolioHolding(
                    fund_code=item.fund_code,
                    shares=item.shares,
                    cost_amount=round(item.amount - item.profit, 2),
                    source="ocr",
                )
            )
        created += 1
    db.commit()
    return {"created_count": created}
