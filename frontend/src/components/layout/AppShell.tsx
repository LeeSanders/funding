import { PropsWithChildren } from "react";

const navItems = ["首页总览", "单基金分析", "持仓估值", "基金推荐", "新闻事件"];

type AppShellProps = PropsWithChildren<{
  title: string;
  subtitle: string;
}>;

export function AppShell({ title, subtitle, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-kicker">Funding</span>
          <strong>正式项目脚手架</strong>
          <p>面向基金分析、推荐、持仓估值与 OCR 的生产化骨架。</p>
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item, index) => (
            <button className={`nav-item ${index === 0 ? "active" : ""}`} key={item} type="button">
              {item}
            </button>
          ))}
        </nav>
      </aside>
      <main className="content-area">
        <header className="page-header">
          <div>
            <span className="page-kicker">Production Scaffold</span>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
