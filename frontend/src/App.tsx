import { useEffect, useMemo, useState } from "react";
import ResumesPage from "./pages/resumes";
import JobsPage from "./pages/jobs";
import DiligencePage from "./pages/diligence";
import RankedJobsPage from "./pages/ranked-jobs";
import MessagesPage from "./pages/messages";
import InboxPage from "./pages/inbox";
import type { JobPosting, WorkflowState, ProviderConfig, ProviderPreset } from "./lib/types";
import { loadWorkflowState, saveWorkflowState } from "./lib/workflowState";
import {
  getProviderConfig,
  getProviderPresets,
  saveProviderConfig,
  clearProviderConfig,
  testProviderConnection,
} from "./lib/api";

type PageKey = "resumes" | "jobs" | "diligence" | "ranked" | "messages" | "inbox";

const pages: Array<{ key: PageKey; label: string }> = [
  { key: "resumes", label: "简历" },
  { key: "jobs", label: "岗位" },
  { key: "diligence", label: "尽调" },
  { key: "ranked", label: "排序" },
  { key: "messages", label: "话术" },
  { key: "inbox", label: "发送箱" },
];

export default function App() {
  const [page, setPage] = useState<PageKey>("resumes");
  const [workflow, setWorkflow] = useState<WorkflowState>(() => loadWorkflowState());

  // —— 设置面板状态 ——
  const [showSettings, setShowSettings] = useState(false);
  const [presets, setPresets] = useState<Record<string, ProviderPreset>>({});
  const [provider, setProvider] = useState("openai");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [baseUrlInput, setBaseUrlInput] = useState("");
  const [modelInput, setModelInput] = useState("");
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [keyMasked, setKeyMasked] = useState("");
  const [keyStatus, setKeyStatus] = useState("");
  const [keyTesting, setKeyTesting] = useState(false);

  useEffect(() => {
    saveWorkflowState(workflow);
  }, [workflow]);

  // 打开设置面板时加载配置
  useEffect(() => {
    if (!showSettings) return;
    // 加载供应商预设
    getProviderPresets().then((r) => setPresets(r.presets)).catch(() => {});
    // 加载当前配置
    getProviderConfig().then((c: ProviderConfig) => {
      setProvider(c.provider || "openai");
      setKeyConfigured(c.configured);
      setKeyMasked(c.masked);
      setBaseUrlInput(c.base_url || "");
      setModelInput(c.model || "");
      setApiKeyInput("");
    }).catch(() => {});
  }, [showSettings]);

  // 切换供应商时自动填入默认 base_url 和 model
  function onProviderChange(p: string) {
    setProvider(p);
    const preset = presets[p];
    if (preset) {
      setBaseUrlInput(preset.base_url || "");
      setModelInput(preset.models?.[0] || "");
    } else {
      setBaseUrlInput("");
      setModelInput("");
    }
    setApiKeyInput("");
    setKeyStatus("");
  }

  async function onSaveKey() {
    if (!apiKeyInput.trim()) return;
    try {
      await saveProviderConfig(provider, apiKeyInput.trim(), baseUrlInput, modelInput);
      setKeyConfigured(true);
      setKeyMasked(apiKeyInput.trim().slice(0, 7) + "****" + apiKeyInput.trim().slice(-4));
      setApiKeyInput("");
      setKeyStatus("已保存");
    } catch (e) {
      setKeyStatus(e instanceof Error ? e.message : "保存失败");
    }
  }

  async function onDeleteKey() {
    try {
      await clearProviderConfig();
      setKeyConfigured(false);
      setKeyMasked("");
      setKeyStatus("已清除");
    } catch (e) {
      setKeyStatus(e instanceof Error ? e.message : "清除失败");
    }
  }

  async function onTestKey() {
    setKeyTesting(true);
    setKeyStatus("");
    try {
      const r = await testProviderConnection();
      setKeyStatus(r.ok ? "✅ 连接成功" : `❌ ${r.message.slice(0, 100)}`);
    } catch (e) {
      setKeyStatus(e instanceof Error ? e.message : "测试失败");
    } finally {
      setKeyTesting(false);
    }
  }

  const selectedJob = workflow.selectedJob;

  const targetTitle = useMemo(() => {
    if (!selectedJob) return "还没有选中目标岗位";
    return selectedJob.title;
  }, [selectedJob]);

  function updateSelectedJob(job: JobPosting | null) {
    setWorkflow((current) => ({ ...current, selectedJob: job }));
  }

  return (
    <div className="workspace-shell" data-testid="workspace-shell">
      <header className="workspace-header">
        <div className="workspace-topline">
          <div className="workspace-brand">
            <div className="workspace-kicker">求职工作台</div>
            <h1 className="workspace-title">BOSS 直聘自动求职工作台</h1>
            <p className="workspace-subtitle">
              先选岗位，再看简历、尽调、排序和话术。每一步都围着同一个目标岗位转，不再到处散。
            </p>
          </div>

          <nav aria-label="主导航" className="workspace-nav" data-testid="workspace-rail">
            {pages.map((item) => (
              <button
                key={item.key}
                type="button"
                className="workspace-tab"
                onClick={() => setPage(item.key)}
                aria-pressed={page === item.key}
              >
                {item.label}
              </button>
            ))}
            <button
              type="button"
              className={`workspace-tab ${showSettings ? "workspace-tab--active" : ""}`}
              onClick={() => setShowSettings(!showSettings)}
              title="API 设置"
              style={{ padding: "10px 12px" }}
            >
              ⚙
            </button>
          </nav>
        </div>

      </header>

      {/* —— 设置面板 —— */}
      {showSettings && (
        <section className="settings-panel">
          <div className="settings-panel__inner">
            <h3 className="section-title-sm">🔑 AI 供应商设置</h3>
            <p className="workspace-target-meta">
              选择 AI 供应商并配置 API Key。Key 仅保存在本地，不会上传到任何第三方。
            </p>

            {/* 供应商选择 */}
            <div className="settings-row">
              <label className="settings-label">供应商</label>
              <select
                className="form-input form-input--inline"
                value={provider}
                onChange={(e) => onProviderChange(e.target.value)}
              >
                {Object.entries(presets).map(([k, v]) => (
                  <option key={k} value={k}>{v.name}</option>
                ))}
                {Object.keys(presets).length === 0 && (
                  <>
                    <option value="openai">OpenAI</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="zhipu">智谱 GLM</option>
                    <option value="moonshot">月之暗面 Moonshot</option>
                    <option value="custom">自定义</option>
                  </>
                )}
              </select>
            </div>

            {/* API Key */}
            <div className="settings-row">
              <label className="settings-label">API Key</label>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flex: 1 }}>
                <input
                  className="form-input form-input--inline"
                  type="password"
                  placeholder="输入 API Key ..."
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && onSaveKey()}
                />
                <button type="button" className="button-primary" onClick={onSaveKey} disabled={!apiKeyInput.trim()}>
                  保存
                </button>
                {keyConfigured && (
                  <button type="button" className="button-secondary" onClick={onDeleteKey}>
                    清除
                  </button>
                )}
              </div>
            </div>

            {/* Base URL（自定义时显示） */}
            <div className="settings-row">
              <label className="settings-label">Base URL</label>
              <input
                className="form-input form-input--inline"
                type="text"
                placeholder={provider === "openai" ? "留空使用默认" : "https://api.example.com/v1"}
                value={baseUrlInput}
                onChange={(e) => setBaseUrlInput(e.target.value)}
              />
            </div>

            {/* 模型选择 */}
            <div className="settings-row">
              <label className="settings-label">模型</label>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flex: 1 }}>
                {presets[provider]?.models?.length ? (
                  <select
                    className="form-input form-input--inline"
                    value={modelInput}
                    onChange={(e) => setModelInput(e.target.value)}
                  >
                    {presets[provider].models.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="form-input form-input--inline"
                    type="text"
                    placeholder="输入模型名，如 gpt-4o-mini"
                    value={modelInput}
                    onChange={(e) => setModelInput(e.target.value)}
                  />
                )}
              </div>
            </div>

            {/* 状态栏 */}
            {keyConfigured && (
              <div className="settings-row" style={{ alignItems: "center" }}>
                <span className="tag tag--active">已配置: {presets[provider]?.name || provider} · {keyMasked}</span>
                <button type="button" className="button-secondary" onClick={onTestKey} disabled={keyTesting}>
                  {keyTesting ? "测试中..." : "测试连接"}
                </button>
              </div>
            )}

            {keyStatus && (
              <p className={`workspace-target-meta ${keyStatus.includes("✅") ? "status-line--success" : ""}`}>
                {keyStatus}
              </p>
            )}
          </div>
        </section>
      )}

      <main className="workspace-stage" data-testid="workspace-stage">
        <div style={{ display: page === "resumes" ? "block" : "none", overflow: "visible" }}>
          <ResumesPage selectedJob={selectedJob} />
        </div>
        <div style={{ display: page === "jobs" ? "block" : "none" }}>
          <JobsPage selectedJobId={selectedJob?.id || null} onSelectJob={updateSelectedJob} />
        </div>
        <div style={{ display: page === "diligence" ? "block" : "none" }}>
          <DiligencePage />
        </div>
        <div style={{ display: page === "ranked" ? "block" : "none" }}>
          <RankedJobsPage />
        </div>
        <div style={{ display: page === "messages" ? "block" : "none" }}>
          <MessagesPage />
        </div>
        <div style={{ display: page === "inbox" ? "block" : "none" }}>
          <InboxPage />
        </div>
      </main>
    </div>
  );
}
