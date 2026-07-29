import { useState, useEffect, useRef } from "react";
import type { ProviderConfig, ProviderPreset } from "../lib/types";
import {
  getProviderConfig, getProviderPresets, saveProviderConfig,
  clearProviderConfig, testProviderConnection,
  getBaiduConfig, saveBaiduConfig, deleteBaiduConfig, testBaiduConnection,
  getBusinessConfig, saveBusinessConfig, deleteBusinessConfig, testBusinessConnection,
  applyJobsImport, exportSettings,
  clearLocalDataPackage,
  getOnboardingWizard, getUserPreferences,
  importSettings, jobsImportTemplateUrl, previewJobsImport,
  saveUserPreferences,
} from "../lib/api";
import { clearLocalWorkflowStorage } from "../lib/store";
import type { JobsImportWizard, OnboardingWizard, UserPreferences } from "../lib/types";

// 内置默认预设 — 即使 API 延迟也能立刻显示
const DEFAULT_PRESETS: Record<string, ProviderPreset> = {
  openai: { name: "OpenAI", base_url: "", models: ["gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"] },
  deepseek: { name: "DeepSeek", base_url: "https://api.deepseek.com", models: ["deepseek-chat", "deepseek-reasoner"] },
  zhipu: { name: "智谱 GLM", base_url: "https://open.bigmodel.cn/api/paas/v4", models: ["glm-4-flash", "glm-4-plus"] },
  moonshot: { name: "月之暗面", base_url: "https://api.moonshot.cn/v1", models: ["moonshot-v1-8k", "moonshot-v1-32k"] },
  custom: { name: "自定义", base_url: "", models: [] },
};

let _cachePresets: Record<string, ProviderPreset> | null = null;
let _cacheProvider: { provider: string; configured: boolean; masked: string; base_url: string; model: string } | null = null;
let _cacheBaidu: { configured: boolean; masked: string } | null = null;
export default function SettingsPanel({ show, onClose }: { show: boolean; onClose: () => void }) {
  const [presets, setPresets] = useState<Record<string, ProviderPreset>>(_cachePresets || DEFAULT_PRESETS);
  const [provider, setProvider] = useState(_cacheProvider?.provider || "openai");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [baseUrlInput, setBaseUrlInput] = useState(_cacheProvider?.base_url || "");
  const [modelInput, setModelInput] = useState(_cacheProvider?.model || "");
  const [keyConfigured, setKeyConfigured] = useState(_cacheProvider?.configured || false);
  const [keyMasked, setKeyMasked] = useState(_cacheProvider?.masked || "");
  const [keyStatus, setKeyStatus] = useState("");
  const [keyTesting, setKeyTesting] = useState(false);
  const [baiduConfigured, setBaiduConfigured] = useState(_cacheBaidu?.configured || false);
  const [baiduMasked, setBaiduMasked] = useState(_cacheBaidu?.masked || "");
  const [baiduApiKey, setBaiduApiKey] = useState("");
  const [baiduStatus, setBaiduStatus] = useState("");
  const [baiduTesting, setBaiduTesting] = useState(false);
  const [bizConfigured, setBizConfigured] = useState(false);
  const [bizMasked, setBizMasked] = useState("");
  const [bizSidInput, setBizSidInput] = useState("");
  const [bizSkeyInput, setBizSkeyInput] = useState("");
  const [bizEndpointInput, setBizEndpointInput] = useState("");
  const [bizStatus, setBizStatus] = useState("");
  const [bizTesting, setBizTesting] = useState(false);
  const [backupStatus, setBackupStatus] = useState("");
  const [localDataStatus, setLocalDataStatus] = useState("");
  const [clearingLocalPackage, setClearingLocalPackage] = useState(false);
  const [preferences, setPreferences] = useState<UserPreferences>({ stability: 50, salary: 50, growth: 50, match: 50, avoid_industries: [], preferred_cities: [] });
  const [preferenceStatus, setPreferenceStatus] = useState("");
  const [onboardingWizard, setOnboardingWizard] = useState<OnboardingWizard | null>(null);
  const [importText, setImportText] = useState("");
  const [importPreview, setImportPreview] = useState<JobsImportWizard | null>(null);
  const [importStatus, setImportStatus] = useState("");
  const settingsImportRef = useRef<HTMLInputElement>(null);
  const mountedRef = useRef(true);
  useEffect(() => {
    if (!show) return;
    mountedRef.current = true;
    Promise.all([getProviderPresets(), getProviderConfig(), getBaiduConfig(), getBusinessConfig(), getUserPreferences(), getOnboardingWizard()])
      .then(([pr, pc, bc, biz, pref, wizard]) => {
        if (!mountedRef.current) return;
        _cachePresets = pr.presets; _cacheProvider = pc; _cacheBaidu = bc;
        setPresets(pr.presets); setProvider(pc.provider || "openai");
        setKeyConfigured(pc.configured); setKeyMasked(pc.masked);
        setBaseUrlInput(pc.base_url || ""); setModelInput(pc.model || "");
        setBaiduConfigured(bc.configured); setBaiduMasked(bc.masked);
        setBizConfigured(biz.configured); setBizMasked(biz.masked); setBizEndpointInput(biz.endpoint || "");
        setPreferences(pref.preferences);
        setOnboardingWizard(wizard);
      }).catch(() => {});
    return () => { mountedRef.current = false; };
  }, [show]);

  async function onSaveKey() {
    if (!apiKeyInput.trim()) return;
    try {
      await saveProviderConfig(provider, apiKeyInput.trim(), baseUrlInput, modelInput);
      const masked = apiKeyInput.trim().slice(0, 7) + "****" + apiKeyInput.trim().slice(-4);
      setKeyConfigured(true); setKeyMasked(masked); setApiKeyInput(""); setKeyStatus("已保存");
      _cacheProvider = { provider, configured: true, masked, base_url: baseUrlInput, model: modelInput };
    } catch (e) { setKeyStatus(e instanceof Error ? e.message : "保存失败"); }
  }
  async function onDeleteKey() {
    try { await clearProviderConfig(); setKeyConfigured(false); setKeyMasked(""); setKeyStatus("已清除"); _cacheProvider = { ...(_cacheProvider || { provider: "openai", base_url: "", model: "" }), configured: false, masked: "" }; } catch (e) { setKeyStatus(e instanceof Error ? e.message : "清除失败"); }
  }
  async function onTestKey() {
    setKeyTesting(true); setKeyStatus("");
    try { const r = await testProviderConnection(); setKeyStatus(r.ok ? "连接成功" : `失败: ${r.message.slice(0, 100)}`); } catch (e) { setKeyStatus(e instanceof Error ? e.message : "测试失败"); }
    finally { setKeyTesting(false); }
  }
  async function onSaveBaidu() {
    if (!baiduApiKey.trim()) return;
    try { const r = await saveBaiduConfig(baiduApiKey.trim()); setBaiduConfigured(true); setBaiduMasked(r.masked); setBaiduApiKey(""); setBaiduStatus("已保存"); _cacheBaidu = { configured: true, masked: r.masked }; } catch (e) { setBaiduStatus(e instanceof Error ? e.message : "保存失败"); }
  }
  async function onDeleteBaidu() {
    try { await deleteBaiduConfig(); setBaiduConfigured(false); setBaiduMasked(""); setBaiduStatus("已清除"); _cacheBaidu = { configured: false, masked: "" }; } catch (e) { setBaiduStatus(e instanceof Error ? e.message : "清除失败"); }
  }
  async function onTestBaidu() {
    setBaiduTesting(true); setBaiduStatus("");
    try { const r = await testBaiduConnection(); setBaiduStatus(r.ok ? "✓ " + r.message : "✗ " + r.message); } catch (e) { setBaiduStatus("✗ " + (e instanceof Error ? e.message : "测试失败")); }
    finally { setBaiduTesting(false); }
  }

  useEffect(() => {
    if (!show) return;
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [show, onClose]);

  if (!show) return null;

  async function onSaveBiz() {
    if (!bizSidInput.trim() || !bizSkeyInput.trim()) return;
    try {
      const r = await saveBusinessConfig(bizSidInput.trim(), bizSkeyInput.trim(), bizEndpointInput.trim());
      setBizConfigured(true); setBizMasked(r.masked); setBizSidInput(""); setBizSkeyInput(""); setBizStatus("已保存");
    } catch (e) { setBizStatus(e instanceof Error ? e.message : "保存失败"); }
  }
  async function onDeleteBiz() {
    try { await deleteBusinessConfig(); setBizConfigured(false); setBizMasked(""); setBizStatus("已清除"); } catch (e) { setBizStatus(e instanceof Error ? e.message : "清除失败"); }
  }
  async function onTestBiz() {
    setBizTesting(true); setBizStatus("");
    try { const r = await testBusinessConnection(); setBizStatus(r.ok ? r.message : `失败: ${r.message.slice(0, 100)}`); } catch (e) { setBizStatus(e instanceof Error ? e.message : "测试失败"); }
    finally { setBizTesting(false); }
  }

  function downloadJson(filename: string, payload: unknown) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function onExportSettings(includeSecret: boolean) {
    if (includeSecret && !confirm("完整备份会包含 API 密钥，请确认只保存在可信位置。")) return;
    try {
      const payload = await exportSettings(includeSecret);
      downloadJson(includeSecret ? "boss-workbench-settings-full.json" : "boss-workbench-settings-masked.json", payload);
      setBackupStatus(includeSecret ? "完整配置已导出" : "脱敏配置已导出");
    } catch (e) {
      setBackupStatus(e instanceof Error ? e.message : "配置导出失败");
    }
  }

  async function onImportSettings(file?: File) {
    if (!file) return;
    try {
      const payload = JSON.parse(await file.text());
      const result = await importSettings(payload);
      setBackupStatus(result.imported.length ? `已导入：${result.imported.join("、")}` : "导入文件不含可恢复密钥，未覆盖现有配置");
      const [pc, bc, biz] = await Promise.all([getProviderConfig(), getBaiduConfig(), getBusinessConfig()]);
      setProvider(pc.provider || "openai"); setKeyConfigured(pc.configured); setKeyMasked(pc.masked);
      setBaseUrlInput(pc.base_url || ""); setModelInput(pc.model || "");
      setBaiduConfigured(bc.configured); setBaiduMasked(bc.masked);
      setBizConfigured(biz.configured); setBizMasked(biz.masked); setBizEndpointInput(biz.endpoint || "");
    } catch (e) {
      setBackupStatus(e instanceof Error ? e.message : "配置导入失败");
    } finally {
      if (settingsImportRef.current) settingsImportRef.current.value = "";
    }
  }

  async function onSavePreferences() {
    try {
      const saved = await saveUserPreferences(preferences);
      setPreferences(saved.preferences);
      setPreferenceStatus("求职偏好已保存");
    } catch (e) {
      setPreferenceStatus(e instanceof Error ? e.message : "求职偏好保存失败");
    }
  }

  async function onPreviewJobsImport() {
    if (!importText.trim()) {
      setImportStatus("请先粘贴 CSV 或 JSON 岗位数据");
      return;
    }
    try {
      const preview = await previewJobsImport({ text: importText });
      setImportPreview(preview);
      setImportStatus(preview.message);
    } catch (e) {
      setImportStatus(e instanceof Error ? e.message : "导入预览失败");
    }
  }

  async function onApplyJobsImport() {
    if (!importPreview || importPreview.summary.creates === 0) {
      setImportStatus("没有可新增的岗位");
      return;
    }
    try {
      const result = await applyJobsImport({ text: importText });
      setImportPreview(result.preview);
      setImportStatus(`已导入 ${result.imported} 条，跳过 ${result.skipped} 条`);
    } catch (e) {
      setImportStatus(e instanceof Error ? e.message : "导入失败");
    }
  }

  function updatePreferenceNumber(key: "stability" | "salary" | "growth" | "match", value: string) {
    setPreferences(prev => ({ ...prev, [key]: Math.max(0, Math.min(100, Number(value) || 0)) }));
  }

  function updatePreferenceList(key: "avoid_industries" | "preferred_cities", value: string) {
    setPreferences(prev => ({
      ...prev,
      [key]: value.split(/[、,，]/).map(item => item.trim()).filter(Boolean),
    }));
  }

  function onClearLocalData() {
    if (!confirm("确定清除本机页面流程数据？这会清除当前模块、已选岗位、简历解析结果、尽调缓存和对话记录。")) return;
    clearLocalWorkflowStorage();
    setLocalDataStatus("本机页面流程数据已清除，页面将重新载入");
    window.setTimeout(() => window.location.reload(), 300);
  }

  async function onClearLocalDataPackage() {
    const confirmed = confirm(
      "确定清空本地数据包？这会删除岗位池、简历文件、上传附件、尽调结果、排序结果、打招呼记录、浏览器登录态、日志和已保存的 API 配置。此操作不可撤销。"
    );
    if (!confirmed) return;
    const doubleConfirmed = confirm("请再次确认：清空后需要重新登录 BOSS，并重新配置 API Key。继续清空？");
    if (!doubleConfirmed) return;
    setClearingLocalPackage(true);
    setLocalDataStatus("正在清空本地数据包...");
    try {
      const result = await clearLocalDataPackage();
      clearLocalWorkflowStorage();
      setLocalDataStatus(`${result.message}，已删除 ${result.count} 项，页面将重新载入`);
      window.setTimeout(() => window.location.reload(), 600);
    } catch (e) {
      setLocalDataStatus(e instanceof Error ? e.message : "清空本地数据包失败");
    } finally {
      setClearingLocalPackage(false);
    }
  }

  return (
    <section className="settings-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="settings-panel" onClick={e => e.stopPropagation()}>
        <div className="page-section__top">
          <div>
            <div className="page-kicker">设置</div>
            <h2 className="page-title">AI 供应商</h2>
          </div>
          <button type="button" className="button-quiet" onClick={onClose} style={{ fontSize: 18, padding: "4px 8px" }}>✕</button>
        </div>

        <div style={{ marginTop: 16 }}>
          <div className="settings-row">
            <label className="settings-label">供应商</label>
            <select className="form-input form-input--inline" value={provider} onChange={e => setProvider(e.target.value)}>
              {Object.entries(presets).map(([k, v]) => <option key={k} value={k}>{v.name}</option>)}
            </select>
          </div>
          <div className="settings-row">
            <label className="settings-label">API Key</label>
            <div style={{ display: "flex", gap: 8, flex: 1 }}>
              <input className="form-input form-input--inline" type="password"
                placeholder={keyConfigured ? keyMasked : "sk-..."}
                value={apiKeyInput} onChange={e => setApiKeyInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && onSaveKey()} />
              <button type="button" className="button-primary" onClick={onSaveKey} disabled={!apiKeyInput.trim()}>保存</button>
              {keyConfigured && <button type="button" className="button-secondary" onClick={onDeleteKey}>清除</button>}
            </div>
          </div>
          <div className="settings-row">
            <label className="settings-label">Base URL</label>
            <input className="form-input form-input--inline" type="text"
              placeholder={provider === "openai" ? "留空使用默认" : "https://api.example.com/v1"}
              value={baseUrlInput} onChange={e => setBaseUrlInput(e.target.value)} />
          </div>
          <div className="settings-row">
            <label className="settings-label">模型</label>
            <div style={{ display: "flex", gap: 8, flex: 1 }}>
              {presets[provider]?.models?.length ? (
                <select className="form-input form-input--inline" value={modelInput} onChange={e => setModelInput(e.target.value)}>
                  {presets[provider].models.map((m: string) => <option key={m} value={m}>{m}</option>)}
                </select>
              ) : (
                <input className="form-input form-input--inline" type="text" placeholder="输入模型名" value={modelInput} onChange={e => setModelInput(e.target.value)} />
              )}
            </div>
          </div>
          {keyConfigured && (
            <div className="settings-row" style={{ alignItems: "center" }}>
              <span className="tag tag--active">已配置: {presets[provider]?.name || provider} · {keyMasked}</span>
              <button type="button" className="button-secondary" onClick={onTestKey} disabled={keyTesting}>
                {keyTesting ? "测试中..." : "测试连接"}
              </button>
            </div>
          )}
          {keyStatus && <p className="settings-status">{keyStatus}</p>}
        </div>

        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <div className="page-kicker">百度千帆智能搜索</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 8px" }}>
            用于公司尽调的真实互联网搜索 + AI 智能总结。在{" "}
            <a href="https://console.bce.baidu.com/qianfan" target="_blank" rel="noopener" style={{"color":"var(--accent)"}}>百度千帆控制台</a>
            {" "}创建应用获取 API Key。
          </p>
          <div className="settings-row">
            <label className="settings-label">API Key</label>
            <div style={{ display: "flex", gap: 8, flex: 1 }}>
              <input className="form-input form-input--inline" type="password"
                placeholder="千帆 API Key"
                value={baiduApiKey} onChange={e => setBaiduApiKey(e.target.value)}
                onKeyDown={e => e.key === "Enter" && onSaveBaidu()} />
              <button type="button" className="button-primary" onClick={onSaveBaidu} disabled={!baiduApiKey.trim()}>保存</button>
              {baiduConfigured && <button type="button" className="button-secondary" onClick={onDeleteBaidu}>清除</button>}
            </div>
          </div>
          {baiduConfigured && (
            <div className="settings-row" style={{ alignItems: "center", marginTop: 6 }}>
              <span className="tag tag--active">已配置 · {baiduMasked}</span>
              <button type="button" className="button-secondary" onClick={onTestBaidu} disabled={baiduTesting} style={{ fontSize: 12 }}>
                {baiduTesting ? "测试中..." : "测试连接"}
              </button>
            </div>
          )}
          {baiduStatus && <p className="settings-status">{baiduStatus}</p>}
        </div>

        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <div className="page-kicker">腾讯云企业工商 API</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 8px" }}>
            用于公司尽调的结构化工商数据（法人、注册资本、股东、经营异常等）。在{" "}
            <a href="https://market.cloud.tencent.com/products/28760" target="_blank" rel="noopener" style={{"color":"var(--accent)"}}>腾讯云市场</a>
            {" "}订阅企业工商全量查询接口后，到已购产品的资源实例中复制该商品的 secretId/secretKey。
          </p>
          <div className="settings-row">
            <label className="settings-label">资源实例 SecretId</label>
            <div style={{ display: "flex", gap: 8, flex: 1 }}>
              <input className="form-input form-input--inline" type="password"
                placeholder="云市场资源实例 secretId"
                value={bizSidInput} onChange={e => setBizSidInput(e.target.value)} />
            </div>
          </div>
          <div className="settings-row">
            <label className="settings-label">资源实例 SecretKey</label>
            <div style={{ display: "flex", gap: 8, flex: 1 }}>
              <input className="form-input form-input--inline" type="password"
                placeholder="云市场资源实例 secretKey"
                value={bizSkeyInput} onChange={e => setBizSkeyInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && onSaveBiz()} />
              <button type="button" className="button-primary" onClick={onSaveBiz} disabled={!bizSidInput.trim() || !bizSkeyInput.trim()}>保存</button>
              {bizConfigured && <button type="button" className="button-secondary" onClick={onDeleteBiz}>清除</button>}
            </div>
          </div>
          <div className="settings-row">
            <label className="settings-label">API 端点</label>
            <input className="form-input form-input--inline" type="text"
              placeholder="留空使用 https://ap-shanghai.cloudmarket-apigw.com/service-6dr7ul9n/enterprise/business/all"
              value={bizEndpointInput} onChange={e => setBizEndpointInput(e.target.value)} />
          </div>
          {bizConfigured && (
            <div className="settings-row" style={{ alignItems: "center", marginTop: 6 }}>
              <span className="tag tag--active">已配置 · {bizMasked}</span>
              <button type="button" className="button-secondary" onClick={onTestBiz} disabled={bizTesting} style={{ fontSize: 12 }}>
                {bizTesting ? "测试中..." : "测试连接"}
              </button>
            </div>
          )}
          {bizStatus && <p className="settings-status">{bizStatus}</p>}
        </div>

        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <div className="page-kicker">配置备份</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 8px" }}>
            导出 AI、百度搜索、工商 API 配置。默认导出为脱敏备份，完整备份会包含密钥。
          </p>
          <div className="settings-row" style={{ alignItems: "center" }}>
            <label className="settings-label">备份</label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button type="button" className="button-secondary" onClick={() => onExportSettings(false)}>导出脱敏配置</button>
              <button type="button" className="button-secondary" onClick={() => onExportSettings(true)}>导出完整配置</button>
              <button type="button" className="button-primary" onClick={() => settingsImportRef.current?.click()}>导入配置</button>
              <input
                ref={settingsImportRef}
                type="file"
                accept="application/json,.json"
                style={{ display: "none" }}
                onChange={e => onImportSettings(e.target.files?.[0])}
              />
            </div>
          </div>
          {backupStatus && <p className="settings-status">{backupStatus}</p>}
        </div>

        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <div className="page-kicker">岗位导入向导</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 8px" }}>
            支持粘贴 CSV 或 JSON 数组。导入前会先检查重复和无效数据。
          </p>
          <textarea
            className="form-input"
            rows={5}
            value={importText}
            onChange={e => { setImportText(e.target.value); setImportPreview(null); }}
            placeholder={"title,company,city,salary,source_url\n产品经理,示例科技,上海,20-30K,https://..."}
          />
          <div className="settings-row" style={{ alignItems: "center", marginTop: 8 }}>
            <label className="settings-label">导入</label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <a className="button-secondary button-link" href={jobsImportTemplateUrl()} download>下载 CSV 模板</a>
              <button type="button" className="button-secondary" onClick={onPreviewJobsImport}>预览导入</button>
              <button type="button" className="button-primary" onClick={onApplyJobsImport} disabled={!importPreview || importPreview.summary.creates === 0}>执行导入</button>
            </div>
          </div>
          {importPreview && (
            <div className="settings-insight">
              <strong>{importPreview.message}</strong>
              <p>新增 {importPreview.summary.creates} · 重复 {importPreview.summary.duplicates} · 无效 {importPreview.summary.invalid}</p>
              {importPreview.creates[0] && <small>示例：{importPreview.creates[0].company} · {importPreview.creates[0].title}</small>}
            </div>
          )}
          {importStatus && <p className="settings-status">{importStatus}</p>}
        </div>

        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <div className="page-kicker">求职偏好</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 8px" }}>
            用于后续排序、复盘和 AI 建议的个人策略记忆。
          </p>
          <div className="preference-grid">
            <PreferenceInput label="稳定性" value={preferences.stability} onChange={value => updatePreferenceNumber("stability", value)} />
            <PreferenceInput label="薪资" value={preferences.salary} onChange={value => updatePreferenceNumber("salary", value)} />
            <PreferenceInput label="成长" value={preferences.growth} onChange={value => updatePreferenceNumber("growth", value)} />
            <PreferenceInput label="匹配度" value={preferences.match} onChange={value => updatePreferenceNumber("match", value)} />
          </div>
          <div className="settings-row">
            <label className="settings-label">规避行业</label>
            <input className="form-input form-input--inline" value={preferences.avoid_industries.join("、")} onChange={e => updatePreferenceList("avoid_industries", e.target.value)} placeholder="如: 教培、保险" />
          </div>
          <div className="settings-row">
            <label className="settings-label">偏好城市</label>
            <input className="form-input form-input--inline" value={preferences.preferred_cities.join("、")} onChange={e => updatePreferenceList("preferred_cities", e.target.value)} placeholder="如: 上海、杭州" />
          </div>
          <div className="settings-row">
            <label className="settings-label" />
            <button type="button" className="button-primary" onClick={onSavePreferences}>保存偏好</button>
          </div>
          {preferenceStatus && <p className="settings-status">{preferenceStatus}</p>}
        </div>

        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <div className="page-kicker">本机数据</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 8px" }}>
            页面状态只影响当前界面缓存；本地数据包会删除后端保存的岗位、简历、附件、尽调、打招呼记录、登录态、日志和 API 配置。
          </p>
          <div className="settings-row" style={{ alignItems: "center" }}>
            <label className="settings-label">页面状态</label>
            <button type="button" className="button-quiet button-danger" onClick={onClearLocalData}>清除本机流程数据</button>
          </div>
          <div className="settings-row" style={{ alignItems: "center", marginTop: 8 }}>
            <label className="settings-label">数据包</label>
            <button
              type="button"
              className="button-quiet button-danger"
              onClick={onClearLocalDataPackage}
              disabled={clearingLocalPackage}
            >
              {clearingLocalPackage ? "清空中..." : "一键清空本地数据包"}
            </button>
          </div>
          {localDataStatus && <p className="settings-status">{localDataStatus}</p>}
        </div>
      </div>
    </section>
  );
}

function PreferenceInput({ label, value, onChange }: { label: string; value: number; onChange: (value: string) => void }) {
  return (
    <label className="preference-input">
      <span>{label}</span>
      <input className="form-input" type="number" min={0} max={100} value={value} onChange={e => onChange(e.target.value)} />
    </label>
  );
}
