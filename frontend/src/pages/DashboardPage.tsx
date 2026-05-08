export function DashboardPage() {
  const cards = [
    ["基金代码入口", "6 位基金代码作为一级查询入口，贯穿分析、持仓、OCR 与推荐。"],
    ["消息面与技术面", "保留可解释分析结构，支持分项评分、理由和风险提示。"],
    ["估值与 OCR", "支持持仓估值、OCR 识别、待确认入仓和收益跟踪。"],
  ];

  return (
    <section className="panel-grid panel-grid-3">
      {cards.map(([title, desc]) => (
        <article className="panel-card" key={title}>
          <span className="panel-label">模块说明</span>
          <h3>{title}</h3>
          <p>{desc}</p>
        </article>
      ))}
    </section>
  );
}
