import { apiModules, API_BASE_URL } from "./lib/api";

function App() {
  return (
    <div className="workspace-shell">
      <header className="workspace-header">
        <div>
          <span className="panel-label">Frontend Workspace</span>
          <h1>基金分析系统正式前端</h1>
          <p>
            当前已将 `prototype` 页面迁入 `frontend` 项目，先以稳定迁移为主，后续再逐步拆成 React
            组件和页面模块。
          </p>
        </div>
        <div className="workspace-actions">
          <a className="action-btn primary" href="/workspace/index.html" target="_blank" rel="noreferrer">
            打开完整工作台
          </a>
          <a className="action-btn" href={`${API_BASE_URL.replace("/api/v1", "")}/docs`} target="_blank" rel="noreferrer">
            查看后端文档
          </a>
        </div>
      </header>

      <section className="panel-card stack-gap">
        <div className="section-head">
          <div>
            <span className="panel-label">迁移状态</span>
            <h2>Prototype 已并入正式前端项目</h2>
          </div>
          <span className="status-pill">API Base: {API_BASE_URL}</span>
        </div>
        <div className="module-grid">
          {apiModules.map((module) => (
            <article className="module-card" key={module.title}>
              <h3>{module.title}</h3>
              <code>{module.endpoint}</code>
              <p>{module.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel-card stack-gap">
        <div className="section-head">
          <div>
            <span className="panel-label">工作台预览</span>
            <h2>迁移后的 prototype 页面</h2>
          </div>
          <span className="status-pill">Path: /workspace/index.html</span>
        </div>
        <div className="iframe-shell">
          <iframe className="workspace-frame" src="/workspace/index.html" title="基金分析工作台原型" />
        </div>
      </section>
    </div>
  );
}

export default App;
