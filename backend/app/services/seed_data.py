import json


FUNDS = [
    {
        "code": "016370",
        "name": "信澳业绩驱动混合A",
        "fund_type": "混合型-偏股",
        "risk_level": "中高",
        "theme": "AI 算力",
        "company": "信达澳亚基金",
        "latest_nav": 2.31,
        "estimated_nav": 2.3391,
        "estimated_change_rate": 1.26,
        "latest_volume_rank": 2,
    },
    {
        "code": "021933",
        "name": "富国中证通信设备联接A",
        "fund_type": "指数型-股票",
        "risk_level": "高",
        "theme": "AI 算力",
        "company": "富国基金",
        "latest_nav": 2.84,
        "estimated_nav": 2.9019,
        "estimated_change_rate": 2.18,
        "latest_volume_rank": 1,
    },
    {
        "code": "021735",
        "name": "景顺长城沪港深红利成长低波指数E",
        "fund_type": "指数型-股票",
        "risk_level": "中",
        "theme": "红利低波",
        "company": "景顺长城基金",
        "latest_nav": 1.74,
        "estimated_nav": 1.7494,
        "estimated_change_rate": 0.54,
        "latest_volume_rank": 3,
    },
    {
        "code": "000011",
        "name": "华夏大盘精选混合A",
        "fund_type": "混合型-灵活",
        "risk_level": "中高",
        "theme": "大盘均衡",
        "company": "华夏基金",
        "latest_nav": 20.40,
        "estimated_nav": 20.4632,
        "estimated_change_rate": 0.31,
        "latest_volume_rank": 4,
    },
]


def _json_payload(reasons, events, risks):
    return {
        "reasons_json": json.dumps(reasons, ensure_ascii=False),
        "events_json": json.dumps(events, ensure_ascii=False),
        "risks_json": json.dumps(risks, ensure_ascii=False),
    }


ANALYSES = [
    {
        "fund_code": "016370",
        "decision": "可分批关注",
        "confidence": "中高",
        "action": "分批介入",
        "holding_window": "1-3 周",
        "score": 78,
        "technical_score": 76,
        "news_score": 82,
        "risk_score": 34,
        "summary_title": "当前适合分批买入，不建议追高重仓",
        "summary_text": "技术面中期趋势仍偏强，消息面存在持续催化，但短期涨幅已不低，更适合等待回踩或采用分仓进入。",
        "updated_at": "2026-05-06 15:30",
        **_json_payload(
            {
                "summary": [
                    {"title": "趋势仍在上行区间", "text": "20 日趋势斜率为正，阶段高点虽近，但结构没有明显破坏。"},
                    {"title": "消息有效性较高", "text": "最近 3 天连续出现正向产业事件，且与基金风格映射度较高。"},
                    {"title": "更适合分仓而非梭哈", "text": "当前位置并非绝对低位，分批进入可以降低短期波动冲击。"},
                ],
                "technical": [
                    {"title": "中期趋势 76 分", "text": "5/10/20 日均线维持上拐，趋势仍在多头框架内。"},
                    {"title": "动量处于中高位", "text": "近 10 日涨幅较强，但加速度开始放缓。"},
                ],
                "news": [
                    {"title": "主题催化仍然有效", "text": "相关赛道出现持续消息支撑，且事件密度较高。"},
                    {"title": "行业景气叙事强化", "text": "市场对相关方向的风险偏好仍高。"},
                ],
            },
            [
                {"title": "行业景气数据改善", "meta": "利好 | 强度高 | 关联度高 | 近 24h"},
                {"title": "政策表态偏积极", "meta": "利好 | 强度中 | 时效 3 天"},
            ],
            [
                {"title": "短期追高风险", "text": "板块已有一轮快速上涨，继续强追盈亏比下降。"},
                {"title": "消息落地后震荡", "text": "热点资金若切换风格，相关基金回撤会放大。"},
            ],
        ),
    },
    {
        "fund_code": "021933",
        "decision": "建议买入",
        "confidence": "高",
        "action": "顺势布局",
        "holding_window": "2-4 周",
        "score": 84,
        "technical_score": 85,
        "news_score": 88,
        "risk_score": 42,
        "summary_title": "主题、趋势、消息三项共振，适合顺势配置",
        "summary_text": "指数型产品和主题映射清晰，通信设备景气度数据持续走强，消息面和技术面形成共振。",
        "updated_at": "2026-05-06 15:30",
        **_json_payload(
            {
                "summary": [
                    {"title": "指数映射更清晰", "text": "基金与主题指数关联度高，消息面可以更直接作用到表现。"},
                    {"title": "景气信号连续触发", "text": "近 24 小时和近 3 天均有正向数据。"},
                ],
                "technical": [
                    {"title": "趋势强度 85 分", "text": "中期上行斜率陡峭，回撤后修复速度快。"},
                    {"title": "短期相对强弱明显", "text": "相对同类指数基金，动量更强。"},
                ],
                "news": [
                    {"title": "通信设备景气跟踪数据向上", "text": "是当前消息面的核心正向因子。"},
                    {"title": "产业链资本开支预期改善", "text": "市场对后续订单和业绩预期更积极。"},
                ],
            },
            [
                {"title": "通信设备景气跟踪数据向上", "meta": "利好 | 强度高 | 主题 AI 算力 | 近 24h"},
                {"title": "资本开支预期改善", "meta": "利好 | 强度中高 | 时效 3-7 天"},
            ],
            [
                {"title": "主题波动大", "text": "高波动主题回撤幅度可能显著高于稳健型基金。"},
                {"title": "拥挤交易风险", "text": "热点资金过于集中时，容易出现大波动。"},
            ],
        ),
    },
    {
        "fund_code": "021735",
        "decision": "观察中",
        "confidence": "中",
        "action": "等回调观察",
        "holding_window": "1-2 月",
        "score": 72,
        "technical_score": 70,
        "news_score": 68,
        "risk_score": 22,
        "summary_title": "适合稳健配置，但进攻弹性一般",
        "summary_text": "红利低波方向具备防守属性，适合在风格切换期做配置，但当前消息驱动没有成长板块那么强。",
        "updated_at": "2026-05-06 15:30",
        **_json_payload(
            {
                "summary": [
                    {"title": "低波属性明显", "text": "适合不想承受大波动的配置型用户。"},
                    {"title": "红利风格有资金回流", "text": "消息面有小幅改善，但不属于强爆发方向。"},
                ],
                "technical": [
                    {"title": "净值波动较小", "text": "在同类中回撤控制更优，技术形态更平缓。"},
                ],
                "news": [
                    {"title": "红利风格资金回流", "text": "短期对低波方向形成支撑，但持续性仍需观察。"},
                ],
            },
            [{"title": "红利风格资金回流", "meta": "利好 | 强度中 | 主题 红利低波 | 近 24h"}],
            [{"title": "进攻性不足", "text": "如果你想找爆发型机会，这类基金并不占优。"}],
        ),
    },
    {
        "fund_code": "000011",
        "decision": "暂时观望",
        "confidence": "中",
        "action": "暂不追买",
        "holding_window": "等待明确拐点",
        "score": 69,
        "technical_score": 72,
        "news_score": 60,
        "risk_score": 28,
        "summary_title": "底层风格稳定，但当前缺少明显增量催化",
        "summary_text": "基金自身管理较成熟，净值趋势不差，但当前市场偏好更集中在有明确主题催化的方向。",
        "updated_at": "2026-05-06 15:30",
        **_json_payload(
            {
                "summary": [
                    {"title": "底仓稳定", "text": "适合作为长期观察对象，但当前不是效率最高的买点。"},
                    {"title": "消息催化偏弱", "text": "没有进入近期市场主线事件映射的核心名单。"},
                ],
                "technical": [
                    {"title": "趋势不差但不激进", "text": "阶段走势平稳，缺少强突破信号。"},
                ],
                "news": [
                    {"title": "消息面映射度较低", "text": "近期事件与该基金风格没有形成高关联度。"},
                ],
            },
            [{"title": "宏观流动性预期改善", "meta": "中性偏利好 | 强度中 | 近 3 天"}],
            [{"title": "阶段弹性有限", "text": "热点行情中容易跑输主题型基金。"}],
        ),
    },
]


RECOMMENDATIONS = {
    "balanced": {
        "title": "平衡型推荐逻辑",
        "description": "技术面、消息面、稳定性和主题热度均衡打分。",
        "rows": [
            {"fund_code": "021933", "rank": 1, "decision": "建议买入", "score": 84, "reason": "主题热度高，趋势延续，消息面最强", "risk": "短期涨幅偏大"},
            {"fund_code": "016370", "rank": 2, "decision": "可分批关注", "score": 78, "reason": "综合得分均衡，适合平滑介入", "risk": "接近阶段压力位"},
            {"fund_code": "021735", "rank": 3, "decision": "观察中", "score": 72, "reason": "防守属性好，适合作为平衡仓位", "risk": "进攻性较弱"},
        ],
    },
    "steady": {
        "title": "稳健型推荐逻辑",
        "description": "优先回撤控制和稳定性，对主题热度权重下降。",
        "rows": [
            {"fund_code": "021735", "rank": 1, "decision": "可配置", "score": 79, "reason": "低波红利结构稳，适合做组合压舱石", "risk": "上涨弹性有限"},
            {"fund_code": "000011", "rank": 2, "decision": "观察中", "score": 73, "reason": "底仓稳定，适合长期观察", "risk": "短期缺少强催化"},
            {"fund_code": "016370", "rank": 3, "decision": "观察中", "score": 71, "reason": "质量尚可，但短期波动略高于稳健需求", "risk": "不适合急于重仓"},
        ],
    },
    "aggressive": {
        "title": "进取型推荐逻辑",
        "description": "提升趋势和消息面权重，更偏向短中期进攻机会。",
        "rows": [
            {"fund_code": "021933", "rank": 1, "decision": "建议买入", "score": 88, "reason": "指数映射清晰，强趋势最强", "risk": "高波动、高拥挤"},
            {"fund_code": "016370", "rank": 2, "decision": "可分批关注", "score": 80, "reason": "消息面稳定，具备继续上行条件", "risk": "追高时盈亏比下降"},
            {"fund_code": "021735", "rank": 3, "decision": "暂不优先", "score": 65, "reason": "防守型方向，不适合作为主攻仓位", "risk": "弹性偏弱"},
        ],
    },
}


HOLDINGS = [
    {"fund_code": "021933", "shares": 12800, "cost_amount": 36420, "source": "manual"},
    {"fund_code": "016370", "shares": 21000, "cost_amount": 48600, "source": "manual"},
    {"fund_code": "021735", "shares": 16800, "cost_amount": 29280, "source": "ocr"},
    {"fund_code": "000011", "shares": 9000, "cost_amount": 14130, "source": "manual"},
]


VALUATIONS = [
    {"fund_code": "021933", "estimated_nav": 2.9019, "estimated_change_rate": 2.18, "updated_at": "2026-05-06 14:36"},
    {"fund_code": "016370", "estimated_nav": 2.3391, "estimated_change_rate": 1.26, "updated_at": "2026-05-06 14:36"},
    {"fund_code": "021735", "estimated_nav": 1.7494, "estimated_change_rate": 0.54, "updated_at": "2026-05-06 14:36"},
    {"fund_code": "000011", "estimated_nav": 20.4632, "estimated_change_rate": 0.31, "updated_at": "2026-05-06 14:36"},
]


MOCK_OCR = {
    "filename": "portfolio_screenshot.png",
    "created_at": "2026-05-06 14:40",
    "status": "completed",
    "items": [
        {"fund_code": "021933", "fund_name": "富国中证通信设备联接A", "shares": 12800, "amount": 36420, "confidence": "高"},
        {"fund_code": "016370", "fund_name": "信澳业绩驱动混合A", "shares": 21000, "amount": 48600, "confidence": "高"},
        {"fund_code": "021735", "fund_name": "景顺长城沪港深红利成长低波指数E", "shares": 16800, "amount": 29280, "confidence": "中"},
    ],
}
