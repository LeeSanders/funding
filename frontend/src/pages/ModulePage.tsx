type ModulePageProps = {
  title: string;
  items: Array<{ label: string; value: string }>;
};

export function ModulePage({ title, items }: ModulePageProps) {
  return (
    <section className="panel-card">
      <span className="panel-label">{title}</span>
      <div className="info-list">
        {items.map((item) => (
          <div className="info-row" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
