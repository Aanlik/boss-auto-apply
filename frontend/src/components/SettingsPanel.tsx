import { useState, useEffect, useRef } from "react";
import type { ProviderConfig, ProviderPreset } from "../lib/types";
import {
  getProviderConfig, getProviderPresets, saveProviderConfig,
  clearProviderConfig, testProviderConnection,
  getBaiduConfig, saveBaiduConfig, deleteBaiduConfig, testBaiduConnection,
  getBusinessConfig, saveBusinessConfig, deleteBusinessConfig, testBusinessConnection,
  applyJobsImport, applyRetentionRules, backupStorage, cleanupRetention, confirmCleanup, createReleaseRecord, exportFullBackup, exportRedactedBackup, exportSettings, getAiPreferenceProfile, getApiLogs, getCleanupDryRun, getDiagnosticCenter, getMaintenanceLogs, getOnboardingWizard, getOnlineReport, getPdfVisualRegression, getPrivacyScan, getProductionGuard, getReleaseAcceptanceChecklist, getReleaseAcceptanceSuite, getReleaseCheckSuite, getReleaseManifest, getReleaseNotes, getReleasePreflight, getReleaseVersionSnapshot, getRetentionPreview, getRetentionRules, getRuntimeMode, getSecurityAudit, getStorageMigrationWizard, getStorageStatus, getUserPreferences, importFullBackup, importSettings, jobsImportTemplateUrl, listDeletedJobs, listReleaseRecords, migrateStorageToSqlite, previewJobsImport, previewRestoreDrill, previewStorageRestore, restoreDeletedJobs, rollbackStorageToJson, runDependencyAudit, saveRuntimeMode, saveUserPreferences, setPrimaryStorage,
} from "../lib/api";
import { clearLocalWorkflowStorage } from "../lib/store";
import type { AiPreferenceProfile, CleanupDryRun, DependencyAudit, DiagnosticCenter, JobsImportWizard, MaintenanceLogEvent, OnboardingWizard, PdfVisualRegression, PrivacyScan, ReleaseAcceptanceChecklist, ReleaseAcceptanceSuite, ReleaseCheckSuite, ReleaseManifest, ReleaseNotes, ReleasePreflight, ReleaseRecord, ReleaseVersionSnapshot, RuntimeModeStatus, SecurityAudit, StorageMigrationWizard, StorageStatus, UserPreferences } from "../lib/types";

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
  const [maintenanceStatus, setMaintenanceStatus] = useState("");
  const [retentionPreview, setRetentionPreview] = useState<{ expiredJobs: number; failedTasks: number; resumeFiles: number; archivePath: string } | null>(null);
  const [storageStatus, setStorageStatus] = useState<StorageStatus | null>(null);
  const [releasePreflight, setReleasePreflight] = useState<ReleasePreflight | null>(null);
  const [productionGuard, setProductionGuard] = useState<{ mode: string; status: "ok" | "warn" | "error"; locked: boolean; checks: Array<{ key: string; label: string; status: "ok" | "warn" | "error"; message: string; action: string }>; summary: { total: number; ok: number; warn: number } } | null>(null);
  const [retentionRules, setRetentionRules] = useState<{ suspectAfterDays: number; archiveAfterDays: number; autoArchiveEnabled: boolean } | null>(null);
  const [releaseManifest, setReleaseManifest] = useState<ReleaseManifest | null>(null);
  const [releaseNotes, setReleaseNotes] = useState<ReleaseNotes | null>(null);
  const [releaseAcceptance, setReleaseAcceptance] = useState<ReleaseAcceptanceChecklist | null>(null);
  const [releaseSuite, setReleaseSuite] = useState<ReleaseAcceptanceSuite | null>(null);
  const [releaseCheckSuite, setReleaseCheckSuite] = useState<ReleaseCheckSuite | null>(null);
  const [releaseRecords, setReleaseRecords] = useState<ReleaseRecord[]>([]);
  const [versionSnapshot, setVersionSnapshot] = useState<ReleaseVersionSnapshot | null>(null);
  const [securityAudit, setSecurityAudit] = useState<SecurityAudit | null>(null);
  const [privacyScan, setPrivacyScan] = useState<PrivacyScan | null>(null);
  const [cleanupDryRun, setCleanupDryRun] = useState<CleanupDryRun | null>(null);
  const [diagnosticCenter, setDiagnosticCenter] = useState<DiagnosticCenter | null>(null);
  const [dependencyAudit, setDependencyAudit] = useState<DependencyAudit | null>(null);
  const [pdfVisualRegression, setPdfVisualRegression] = useState<PdfVisualRegression | null>(null);
  const [aiPreferenceProfile, setAiPreferenceProfile] = useState<AiPreferenceProfile | null>(null);
  const [storageWizard, setStorageWizard] = useState<StorageMigrationWizard | null>(null);
  const [runtimeMode, setRuntimeMode] = useState<RuntimeModeStatus | null>(null);
  const [onboardingWizard, setOnboardingWizard] = useState<OnboardingWizard | null>(null);
  const [importText, setImportText] = useState("");
  const [importPreview, setImportPreview] = useState<JobsImportWizard | null>(null);
  const [importStatus, setImportStatus] = useState("");
  const [dependencyAuditing, setDependencyAuditing] = useState(false);
  const [maintenanceLogs, setMaintenanceLogs] = useState<MaintenanceLogEvent[]>([]);
  const [apiLogs, setApiLogs] = useState<Array<{ id: string; time: string; category: string; method: string; url: string; statusCode: number; durationMs: number }>>([]);
  const [deletedJobs, setDeletedJobs] = useState<Array<{ id: string; deletedAt: string; job: { title?: string; company?: string } }>>([]);
  const [preferences, setPreferences] = useState<UserPreferences>({ stability: 70, salary: 70, growth: 70, match: 80, avoid_industries: [], preferred_cities: [] });
  const [preferenceStatus, setPreferenceStatus] = useState("");
  const mountedRef = useRef(false);
  const settingsImportRef = useRef<HTMLInputElement | null>(null);
  const fullBackupImportRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!show) return;
    mountedRef.current = true;
    Promise.all([getProviderPresets(), getProviderConfig(), getBaiduConfig(), getBusinessConfig(), getUserPreferences(), getRuntimeMode(), getOnboardingWizard()])
      .then(([pr, pc, bc, biz, pref, mode, wizard]) => {
        if (!mountedRef.current) return;
        _cachePresets = pr.presets; _cacheProvider = pc; _cacheBaidu = bc;
        setPresets(pr.presets); setProvider(pc.provider || "openai");
        setKeyConfigured(pc.configured); setKeyMasked(pc.masked);
        setBaseUrlInput(pc.base_url || ""); setModelInput(pc.model || "");
        setBaiduConfigured(bc.configured); setBaiduMasked(bc.masked);
        setBizConfigured(biz.configured); setBizMasked(biz.masked); setBizEndpointInput(biz.endpoint || "");
        setPreferences(pref.preferences);
        setRuntimeMode(mode);
        setOnboardingWizard(wizard);
      }).catch(() => {});
    refreshMaintenance();
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

  async function refreshMaintenance() {
    const loaders = [
      getRetentionPreview(),
      getStorageStatus(),
      getMaintenanceLogs("", 8),
      getReleasePreflight(),
      getReleaseCheckSuite(),
      getProductionGuard(),
      getRetentionRules(),
      getReleaseManifest(),
      getReleaseNotes(),
      getReleaseAcceptanceChecklist(),
      getReleaseAcceptanceSuite(),
      getReleaseVersionSnapshot(),
      listReleaseRecords(),
      getSecurityAudit(),
      getPrivacyScan(),
      getCleanupDryRun(),
      getDiagnosticCenter(),
      runDependencyAudit(true),
      getPdfVisualRegression(),
      getAiPreferenceProfile(),
      getStorageMigrationWizard(),
      listDeletedJobs(),
    ] as const;
    const results = await Promise.allSettled(loaders);
    const rejected = results.filter(item => item.status === "rejected");
    const valueAt = <T,>(index: number): T | null => {
      const result = results[index];
      return result?.status === "fulfilled" ? (result.value as T) : null;
    };

    const preview = valueAt<NonNullable<typeof retentionPreview>>(0);
    const storage = valueAt<StorageStatus>(1);
    const logs = valueAt<{ events?: MaintenanceLogEvent[] }>(2);
    const preflight = valueAt<ReleasePreflight>(3);
    const checkSuite = valueAt<ReleaseCheckSuite>(4);
    const guard = valueAt<typeof productionGuard>(5);
    const rules = valueAt<NonNullable<typeof retentionRules>>(6);
    const manifest = valueAt<ReleaseManifest>(7);
    const notes = valueAt<ReleaseNotes>(8);
    const acceptance = valueAt<ReleaseAcceptanceChecklist>(9);
    const suite = valueAt<ReleaseAcceptanceSuite>(10);
    const snapshot = valueAt<ReleaseVersionSnapshot>(11);
    const records = valueAt<{ records?: ReleaseRecord[] }>(12);
    const audit = valueAt<SecurityAudit>(13);
    const privacy = valueAt<PrivacyScan>(14);
    const cleanupPreview = valueAt<CleanupDryRun>(15);
    const diagnostics = valueAt<DiagnosticCenter>(16);
    const dependencyDryRun = valueAt<DependencyAudit>(17);
    const pdfVisual = valueAt<PdfVisualRegression>(18);
    const aiProfile = valueAt<AiPreferenceProfile>(19);
    const wizard = valueAt<StorageMigrationWizard>(20);
    const deleted = valueAt<{ jobs?: Array<{ id: string; deletedAt: string; job: { title?: string; company?: string } }> }>(21);

    if (preview) setRetentionPreview(preview);
    if (storage) setStorageStatus(storage);
    if (logs) setMaintenanceLogs(logs.events || []);
    if (preflight) setReleasePreflight(preflight);
    if (checkSuite) setReleaseCheckSuite(checkSuite);
    if (guard) setProductionGuard(guard);
    if (rules) setRetentionRules(rules);
    if (manifest) setReleaseManifest(manifest);
    if (notes) setReleaseNotes(notes);
    if (acceptance) setReleaseAcceptance(acceptance);
    if (suite) setReleaseSuite(suite);
    if (snapshot) setVersionSnapshot(snapshot);
    if (records) setReleaseRecords(records.records || []);
    if (audit) setSecurityAudit(audit);
    if (privacy) setPrivacyScan(privacy);
    if (cleanupPreview) setCleanupDryRun(cleanupPreview);
    if (diagnostics) setDiagnosticCenter(diagnostics);
    if (dependencyDryRun) setDependencyAudit(dependencyDryRun);
    if (pdfVisual) setPdfVisualRegression(pdfVisual);
    if (aiProfile) setAiPreferenceProfile(aiProfile);
    if (wizard) setStorageWizard(wizard);
    if (deleted) setDeletedJobs((deleted.jobs || []).slice(0, 6));
    setMaintenanceStatus(rejected.length > 0 ? `部分维护检查暂不可用：${rejected.length} 项` : "");
    getApiLogs("", 8).then(r => setApiLogs(r.logs || [])).catch(() => {});
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

  async function onChangeRuntimeMode(mode: RuntimeModeStatus["mode"]) {
    try {
      const next = await saveRuntimeMode(mode);
      setRuntimeMode(next);
      setMaintenanceStatus(next.mode === "production" ? "已切换到生产数据模式" : `已切换到${next.dataScope}`);
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "数据模式切换失败");
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
      await refreshMaintenance();
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

  async function onExportFullBackup() {
    if (!confirm("完整备份会导出本地 data 目录内的业务数据，请只保存在可信位置。")) return;
    try {
      const payload = await exportFullBackup();
      downloadJson("boss-workbench-full-backup.json", payload);
      setMaintenanceStatus("完整备份已导出");
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "完整备份导出失败");
    }
  }

  async function onExportRedactedBackup() {
    try {
      const payload = await exportRedactedBackup();
      downloadJson("boss-workbench-redacted-backup.json", payload);
      setMaintenanceStatus("脱敏数据备份已导出，可用于演示或排查问题");
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "脱敏备份导出失败");
    }
  }

  async function onImportFullBackup(file?: File) {
    if (!file) return;
    try {
      const payload = JSON.parse(await file.text());
      const drill = await previewRestoreDrill(payload);
      if (!confirm(`恢复演练：将恢复 ${drill.wouldRestore} 个文件，覆盖 ${drill.wouldOverwrite} 个文件。确认继续导入？`)) return;
      const result = await importFullBackup(payload);
      setMaintenanceStatus(`完整备份恢复完成：${result.restored} 个文件，跳过 ${result.skipped} 个`);
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "完整备份导入失败");
    } finally {
      if (fullBackupImportRef.current) fullBackupImportRef.current.value = "";
    }
  }

  async function onExportOnlineReport() {
    try {
      const report = await getOnlineReport();
      downloadJson("boss-workbench-online-report.json", report);
      setMaintenanceStatus("上线报告已导出");
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "上线报告导出失败");
    }
  }

  async function onCleanupRetention() {
    if (!confirm("确认归档疑似过期岗位？归档后岗位池中将不再展示这些岗位。")) return;
    try {
      const result = await cleanupRetention({ archive_expired_jobs: true });
      setMaintenanceStatus(`已归档 ${result.archivedJobs} 个疑似过期岗位`);
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "数据保留策略执行失败");
    }
  }

  async function onConfirmCleanup() {
    if (!cleanupDryRun) await refreshMaintenance();
    if (!confirm("确认执行清理？系统会优先归档疑似过期岗位、失败任务和旧简历对话，并保留恢复路径。")) return;
    try {
      const result = await confirmCleanup({
        archive_expired_jobs: true,
        archive_failed_tasks: true,
        archive_resume_chats: true,
      });
      setMaintenanceStatus(`清理完成：归档岗位 ${result.archivedJobs}，失败任务 ${result.archivedTasks}，对话缓存 ${result.archivedChats}`);
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "确认清理失败");
    }
  }

  async function onRunReleaseCheckSuite() {
    try {
      const result = await getReleaseCheckSuite();
      setReleaseCheckSuite(result);
      setMaintenanceStatus(result.status === "ok" ? "发布检查通过，手动门禁仍需执行" : "发布检查完成，请处理关注项");
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "发布检查失败");
    }
  }

  async function onCreateReleaseRecord() {
    const version = window.prompt("发布版本号", versionSnapshot?.version || releaseNotes?.version || "1.0");
    if (!version?.trim()) return;
    const operator = window.prompt("验收人/发布人", "用户") || "";
    const decision = window.confirm("本次是否允许上线？") ? "ready" : "review";
    try {
      const result = await createReleaseRecord({
        version: version.trim(),
        operator: operator.trim(),
        decision,
        notes: [decision === "ready" ? "发布检查后允许上线" : "发布前继续复核"],
      });
      setReleaseRecords(prev => [result.record, ...prev]);
      setMaintenanceStatus(`发布记录已生成：${result.record.version}`);
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "发布记录生成失败");
    }
  }

  async function onApplyRetentionRules() {
    try {
      const result = await applyRetentionRules({
        suspect_after_days: retentionRules?.suspectAfterDays || 30,
        archive_after_days: retentionRules?.archiveAfterDays || 90,
        auto_archive_enabled: false,
      });
      setMaintenanceStatus(`已标记 ${result.markedSuspected} 个疑似过期岗位`);
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "长期维护规则执行失败");
    }
  }

  async function onMigrateStorage() {
    if (!confirm("确认执行 SQLite 快照迁移？迁移前建议先导出完整数据备份。")) return;
    try {
      await migrateStorageToSqlite();
      setMaintenanceStatus("SQLite 快照迁移完成");
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "SQLite 迁移失败");
    }
  }

  async function onRollbackStorage() {
    if (!confirm("确认从 SQLite 快照回滚 JSON 数据？这会覆盖同名 JSON 文件。")) return;
    try {
      await rollbackStorageToJson();
      setMaintenanceStatus("SQLite 快照已回滚到 JSON");
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "SQLite 回滚失败");
    }
  }

  async function onBackupStorage() {
    try {
      const result = await backupStorage();
      setMaintenanceStatus(`SQLite 备份已创建：${result.path}`);
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "SQLite 备份失败");
    }
  }

  async function onRunDependencyAudit() {
    setDependencyAuditing(true);
    setMaintenanceStatus("正在执行依赖审计...");
    try {
      const result = await runDependencyAudit(false);
      setDependencyAudit(result);
      setMaintenanceStatus(result.status === "ok" ? "依赖审计通过" : "依赖审计发现需要关注的项目");
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "依赖审计失败");
    } finally {
      setDependencyAuditing(false);
    }
  }

  async function onRunRepairAction(action: NonNullable<DiagnosticCenter["repairActions"][number]["repairAction"]>) {
    if (action.type === "export_redacted_backup") {
      await onExportRedactedBackup();
      return;
    }
    if (action.type === "refresh_endpoint") {
      setMaintenanceStatus("已刷新诊断检查");
      await refreshMaintenance();
      return;
    }
    setMaintenanceStatus(action.page ? `请前往「${pageLabel(action.page)}」处理：${action.description}` : action.description);
  }

  async function onPreviewStorageRestore() {
    const path = storageStatus?.sqlite.backups[0]?.path;
    if (!path) {
      setMaintenanceStatus("暂无可预览的 SQLite 备份");
      return;
    }
    try {
      const result = await previewStorageRestore(path);
      setMaintenanceStatus(result.valid ? `备份可恢复：${path}` : `备份不可恢复：${result.message || "完整性检查失败"}`);
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "备份预览失败");
    }
  }

  async function onSetPrimaryStorage(activeStore: "json" | "sqlite") {
    const label = activeStore === "sqlite" ? "SQLite" : "JSON";
    if (!confirm(`确认将岗位池主存储切换为 ${label}？切换前建议先导出完整数据备份。`)) return;
    try {
      await setPrimaryStorage(activeStore);
      setMaintenanceStatus(`岗位池主存储已切换为 ${label}`);
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "主存储切换失败");
    }
  }

  async function onRestoreDeletedJob(jobId: string) {
    try {
      const result = await restoreDeletedJobs([jobId]);
      setMaintenanceStatus(`已恢复 ${result.restored} 个岗位`);
      await refreshMaintenance();
    } catch (e) {
      setMaintenanceStatus(e instanceof Error ? e.message : "岗位恢复失败");
    }
  }

  function onClearLocalData() {
    if (!confirm("确定清除本机页面流程数据？这会清除当前模块、已选岗位、简历解析结果、尽调缓存和对话记录。")) return;
    clearLocalWorkflowStorage();
    setBackupStatus("本机页面流程数据已清除，页面将重新载入");
    window.setTimeout(() => window.location.reload(), 300);
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
          <div className="page-kicker">数据模式</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 8px" }}>
            用于区分生产使用、演示调试和自动化测试，避免示例数据误混入正式岗位池。
          </p>
          <div className="settings-row">
            <label className="settings-label">当前模式</label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <select
                className="form-input form-input--inline"
                value={runtimeMode?.mode || "production"}
                disabled={!!runtimeMode?.lockedByEnv}
                onChange={e => onChangeRuntimeMode(e.target.value as RuntimeModeStatus["mode"])}
              >
                <option value="production">上线模式</option>
                <option value="demo">演示模式</option>
                <option value="test">测试模式</option>
              </select>
              {runtimeMode && <span className={`tag ${runtimeMode.mode === "production" ? "tag--active" : "tag--muted"}`}>{runtimeMode.mode === "production" ? "上线模式" : runtimeMode.dataScope}</span>}
            </div>
          </div>
          {runtimeMode?.warning && <p className="settings-status">{runtimeMode.warning}</p>}
          {onboardingWizard && (
            <div className="settings-insight">
              <strong>{onboardingWizard.title} · {onboardingWizard.progress?.percent ?? 0}%</strong>
              <p>下一步：{onboardingWizard.nextStep.label} · {onboardingWizard.nextStep.reason}</p>
              <small>{onboardingWizard.tips[0]}</small>
            </div>
          )}
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
          {aiPreferenceProfile && (
            <div className="settings-insight">
              <strong>AI 反馈画像</strong>
              <p>
                累计反馈 {aiPreferenceProfile.summary.total} 条 · 公司风险倾向 {aiPreferenceProfile.weightHints.company} · 匹配倾向 {aiPreferenceProfile.weightHints.match}
              </p>
              {aiPreferenceProfile.recentNeeds.length > 0 && <small>{aiPreferenceProfile.recentNeeds.slice(0, 2).join("；")}</small>}
            </div>
          )}
        </div>

        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <div className="page-kicker">完整数据维护</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 8px" }}>
            用于上线前备份、迁移前保护、疑似过期岗位归档和本地日志排查。
          </p>
          {releaseCheckSuite && (
            <div className={`release-preflight release-preflight--${releaseCheckSuite.status}`}>
              <div className="release-preflight__summary">
                <strong>一键发布前检查</strong>
                <span>
                  正常 {releaseCheckSuite.summary.ok} · 关注 {releaseCheckSuite.summary.warn} · 异常 {releaseCheckSuite.summary.error} · 手动 {releaseCheckSuite.summary.manual}
                </span>
                <button type="button" className="button-secondary button-secondary--sm" onClick={onRunReleaseCheckSuite}>重新检查</button>
                <button type="button" className="button-primary button-secondary--sm" onClick={onCreateReleaseRecord}>生成发布记录</button>
              </div>
              <div className="release-preflight__checks">
                {releaseCheckSuite.checks.map(check => (
                  <div key={check.key} className={`release-check release-check--${check.status === "manual" ? "warn" : check.status}`}>
                    <span>{check.label}</span>
                    <strong>{check.status === "manual" ? "需手动" : check.status === "ok" ? "正常" : check.status === "error" ? "异常" : "关注"}</strong>
                    <p>{check.command || (check.summary ? JSON.stringify(check.summary) : "等待检查")}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {diagnosticCenter && (
            <div className={`release-preflight release-preflight--${diagnosticCenter.status}`}>
              <div className="release-preflight__summary">
                <strong>错误诊断中心</strong>
                <span>正常 {diagnosticCenter.summary.ok} · 关注 {diagnosticCenter.summary.warn} · 异常 {diagnosticCenter.summary.error}</span>
                <button type="button" className="button-secondary button-secondary--sm" onClick={refreshMaintenance}>重新诊断</button>
              </div>
              <div className="release-preflight__checks">
                {diagnosticCenter.checks.slice(0, 8).map(check => (
                  <div key={check.key} className={`release-check release-check--${check.status}`}>
                    <span>{check.label}</span>
                    <strong>{check.status === "ok" ? "正常" : check.status === "error" ? "异常" : "关注"}</strong>
                    <p>{check.message}</p>
                    {check.action && <em>{check.action}</em>}
                    {check.repairAction && <em>修复：{check.repairAction.label}</em>}
                  </div>
                ))}
              </div>
              {diagnosticCenter.repairActions.length > 0 && (
                <div className="toolbar-row toolbar-row--wrap" style={{ marginTop: 10 }}>
                  {diagnosticCenter.repairActions.slice(0, 6).map(item => (
                    <button key={item.key} type="button" className="button-secondary button-secondary--sm" onClick={() => onRunRepairAction(item.repairAction)}>
                      {item.repairAction.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {releasePreflight && (
            <div className={`release-preflight release-preflight--${releasePreflight.status}`}>
              <div className="release-preflight__summary">
                <strong>{releaseStatusLabel(releasePreflight.status)}</strong>
                <span>
                  共 {releasePreflight.summary.total} 项 · 正常 {releasePreflight.summary.ok} · 关注 {releasePreflight.summary.warn} · 异常 {releasePreflight.summary.error}
                </span>
                <button type="button" className="button-secondary button-secondary--sm" onClick={refreshMaintenance}>一键上线体检</button>
                <button type="button" className="button-secondary button-secondary--sm" onClick={onExportOnlineReport}>导出上线报告</button>
              </div>
              <div className="release-preflight__checks">
                {releasePreflight.checks.slice(0, 8).map(check => (
                  <div key={check.key} className={`release-check release-check--${check.status}`}>
                    <span>{check.label}</span>
                    <strong>{check.status === "ok" ? "正常" : check.status === "error" ? "异常" : "关注"}</strong>
                    <p>{check.message}</p>
                    {check.action && <em>{check.action}</em>}
                  </div>
                ))}
              </div>
            </div>
          )}
          {(releaseSuite || versionSnapshot || privacyScan) && (
            <div className={`release-preflight release-preflight--${releaseSuite?.status || privacyScan?.status || "ok"}`}>
              <div className="release-preflight__summary">
                <strong>上线验收包</strong>
                <span>
                  {versionSnapshot ? `版本 ${versionSnapshot.version}` : "版本快照加载中"} ·
                  隐私命中 {privacyScan?.summary.hits ?? 0} ·
                  验收项 {releaseSuite?.sections.reduce((sum, section) => sum + section.total, 0) ?? 0}
                </span>
                <button type="button" className="button-secondary button-secondary--sm" onClick={refreshMaintenance}>刷新验收包</button>
              </div>
              <div className="release-preflight__checks">
                {releaseSuite?.machineChecks.map(check => (
                  <div key={check.key} className={`release-check release-check--${check.status}`}>
                    <span>{check.label}</span>
                    <strong>{check.status === "ok" ? "正常" : check.status === "error" ? "异常" : "关注"}</strong>
                    <p>{check.summary ? JSON.stringify(check.summary) : "等待人工验收"}</p>
                  </div>
                ))}
                {privacyScan && privacyScan.hits.slice(0, 3).map(hit => (
                  <div key={hit.path} className="release-check release-check--warn">
                    <span>{hit.path}</span>
                    <strong>隐私字段</strong>
                    <p>{hit.fields.join("、")}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {productionGuard && (
            <div className={`release-preflight release-preflight--${productionGuard.status}`}>
              <div className="release-preflight__summary">
                <strong>生产模式保护</strong>
                <span>当前 {productionGuard.mode} · 正常 {productionGuard.summary.ok}/{productionGuard.summary.total}</span>
                <button type="button" className="button-secondary button-secondary--sm" onClick={refreshMaintenance}>刷新保护状态</button>
              </div>
              <div className="release-preflight__checks">
                {productionGuard.checks.map(check => (
                  <div key={check.key} className={`release-check release-check--${check.status}`}>
                    <span>{check.label}</span>
                    <strong>{check.status === "ok" ? "正常" : "关注"}</strong>
                    <p>{check.message}</p>
                    <em>{check.action}</em>
                  </div>
                ))}
              </div>
            </div>
          )}
          {(releaseManifest || securityAudit) && (
            <div className="release-preflight release-preflight--ok">
              <div className="release-preflight__summary">
                <strong>发布清单</strong>
                <span>
                  {releaseManifest ? `门禁 ${releaseManifest.qualityGates.length} 项` : "清单加载中"} ·
                  安全审计 {securityAudit ? releaseStatusLabel(securityAudit.status) : "加载中"}
                </span>
              </div>
              {securityAudit && (
                <div className="release-preflight__checks">
                  {securityAudit.checks.map(check => (
                    <div key={check.key} className={`release-check release-check--${check.status}`}>
                      <span>{check.label}</span>
                      <strong>{check.status === "ok" ? "正常" : check.status === "error" ? "异常" : "关注"}</strong>
                      <p>{check.message}</p>
                    </div>
                  ))}
                </div>
              )}
              {dependencyAudit && (
                <div className="dependency-audit">
                  <div className="dependency-audit__top">
                    <strong>真实依赖审计</strong>
                    <span>{dependencyAudit.dryRun ? "预检查" : releaseStatusLabel(dependencyAudit.status)}</span>
                    <button type="button" className="button-secondary button-secondary--sm" onClick={onRunDependencyAudit} disabled={dependencyAuditing}>
                      {dependencyAuditing ? "审计中..." : "运行审计"}
                    </button>
                  </div>
                  <div className="dependency-audit__grid">
                    {dependencyAudit.checks.map(check => (
                      <div key={check.key} className={`release-check release-check--${check.status}`}>
                        <span>{check.label}</span>
                        <strong>{check.status === "ok" ? "正常" : check.status === "error" ? "异常" : "关注"}</strong>
                        <p>{check.message}</p>
                        {check.command && <em>{check.command}</em>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {pdfVisualRegression && (
                <div className="dependency-audit">
                  <div className="dependency-audit__top">
                    <strong>PDF 真实渲染检查</strong>
                    <span>{releaseStatusLabel(pdfVisualRegression.status)}</span>
                  </div>
                  <div className="dependency-audit__grid">
                    {Object.entries(pdfVisualRegression.checks).map(([key, check]) => (
                      <div key={key} className={`release-check release-check--${check.status === "unavailable" ? "warn" : check.status}`}>
                        <span>{key === "resume" ? "简历 PDF" : "AI 报告 PDF"}</span>
                        <strong>{check.status === "ok" ? "已渲染" : "需关注"}</strong>
                        <p>{check.pages[0] ? `页面 ${check.pages[0].width}x${check.pages[0].height} · 墨迹 ${Math.round(check.pages[0].nonWhiteRatio * 1000) / 10}%` : check.reason || "暂无截图"}</p>
                        {check.previewDataUrl && <img className="pdf-visual-thumb" src={check.previewDataUrl} alt={key === "resume" ? "简历 PDF 缩略图" : "AI 报告 PDF 缩略图"} />}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {cleanupDryRun && (
            <div className={`release-preflight release-preflight--${cleanupDryRun.status}`}>
              <div className="release-preflight__summary">
                <strong>数据清理预演</strong>
                <span>
                  过期岗位 {cleanupDryRun.summary.expiredJobs} · 失败任务 {cleanupDryRun.summary.failedTasks} · 对话缓存 {cleanupDryRun.summary.resumeChats} · 临时文件 {cleanupDryRun.summary.cacheFiles}
                </span>
                <button type="button" className="button-secondary button-secondary--sm" onClick={refreshMaintenance}>刷新预演</button>
                <button type="button" className="button-secondary button-secondary--sm" onClick={onConfirmCleanup}>确认清理</button>
              </div>
              <div className="release-preflight__checks">
                {cleanupDryRun.targets.map(target => (
                  <div key={target.key} className={`release-check release-check--${target.count ? "warn" : "ok"}`}>
                    <span>{target.label}</span>
                    <strong>{target.count}</strong>
                    <p>{target.action}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {releaseRecords.length > 0 && (
            <div className="maintenance-log-list">
              {releaseRecords.slice(0, 3).map(record => (
                <div key={record.id} className="maintenance-log-item">
                  <span>发布记录 · {record.version}</span>
                  <p>{record.operator} · {record.decision === "ready" ? "允许上线" : "继续复核"} · {record.checkSuite.status}</p>
                  <time>{record.createdAt.slice(0, 19).replace("T", " ")}</time>
                </div>
              ))}
            </div>
          )}
          {releaseNotes && (
            <div className="release-notes">
              <div className="release-notes__top">
                <strong>版本 {releaseNotes.version}</strong>
                <span>{releaseNotes.phase}</span>
              </div>
              <div className="release-notes__grid">
                <div>
                  <span>本版亮点</span>
                  <ul>{releaseNotes.highlights.map(item => <li key={item}>{item}</li>)}</ul>
                </div>
                <div>
                  <span>上线注意</span>
                  <ul>{releaseNotes.knownRisks.map(item => <li key={item}>{item}</li>)}</ul>
                </div>
              </div>
            </div>
          )}
          <div className="settings-row" style={{ alignItems: "center" }}>
            <label className="settings-label">完整备份</label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button type="button" className="button-secondary" onClick={onExportFullBackup}>导出完整数据</button>
              <button type="button" className="button-secondary" onClick={onExportRedactedBackup}>导出脱敏数据</button>
              <button type="button" className="button-primary" onClick={() => fullBackupImportRef.current?.click()}>导入完整数据</button>
              <input
                ref={fullBackupImportRef}
                type="file"
                accept="application/json,.json"
                style={{ display: "none" }}
                onChange={e => onImportFullBackup(e.target.files?.[0])}
              />
            </div>
          </div>
          {releaseAcceptance && (
            <details className="release-acceptance">
              <summary>
                <span>上线人工验收清单</span>
                <em>{releaseAcceptance.sections.reduce((total, section) => total + section.steps.length, 0)} 项</em>
              </summary>
              <div className="release-acceptance__grid">
                {releaseAcceptance.sections.map(section => (
                  <div key={section.key} className="release-acceptance__section">
                    <strong>{section.title}</strong>
                    <ol>
                      {section.steps.map(step => <li key={step}>{step}</li>)}
                    </ol>
                  </div>
                ))}
              </div>
            </details>
          )}
          <div className="settings-row" style={{ alignItems: "center" }}>
            <label className="settings-label">保留策略</label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <span className="tag">疑似过期 {retentionPreview?.expiredJobs ?? 0}</span>
              <span className="tag tag--muted">失败任务 {retentionPreview?.failedTasks ?? 0}</span>
              {retentionRules && <span className="tag tag--muted">{retentionRules.suspectAfterDays} 天标记 · {retentionRules.archiveAfterDays} 天归档</span>}
              <button type="button" className="button-secondary" onClick={onApplyRetentionRules}>应用长期规则</button>
              <button type="button" className="button-secondary" onClick={onCleanupRetention}>归档过期岗位</button>
            </div>
          </div>
          {storageStatus && (
            <>
              <p className="settings-status">
                当前存储：{storageStatus.activeStore.toUpperCase()} · SQLite 路径：{storageStatus.sqlite.path} · {storageStatus.sqlite.message}
              </p>
              {storageWizard && (
                <div className="migration-wizard">
                  <div className="migration-wizard__top">
                    <strong>数据迁移向导</strong>
                    <span>{storageWizard.nextStep.label} · {storageWizard.nextStep.action}</span>
                  </div>
                  <div className="migration-wizard__steps">
                    {storageWizard.steps.map(step => (
                      <div key={step.key} className={`migration-step migration-step--${step.status}`}>
                        <strong>{step.label}</strong>
                        <span>{migrationStatusLabel(step.status)}</span>
                        <p>{step.action}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="storage-health-strip">
                <span>Schema v{storageStatus.sqlite.schemaVersion}/{storageStatus.sqlite.targetSchemaVersion}</span>
                <span className={`tag ${storageStatus.sqlite.integrity.status === "ok" ? "tag--success" : "tag--muted"}`}>
                  完整性：{storageStatus.sqlite.integrity.status === "ok" ? "正常" : storageStatus.sqlite.integrity.status}
                </span>
                <span>备份 {storageStatus.sqlite.backups.length} 个</span>
              </div>
              <div className="settings-row" style={{ alignItems: "center" }}>
                <label className="settings-label">SQLite</label>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button type="button" className="button-secondary" onClick={onMigrateStorage}>执行快照迁移</button>
                  <button type="button" className="button-secondary" onClick={onBackupStorage}>创建数据库备份</button>
                  <button type="button" className="button-quiet" onClick={onPreviewStorageRestore}>预览最近备份</button>
                  <button type="button" className="button-secondary" onClick={() => onSetPrimaryStorage("sqlite")}>设为主存储</button>
                  <button type="button" className="button-quiet" onClick={() => onSetPrimaryStorage("json")}>使用 JSON</button>
                  <button type="button" className="button-quiet" onClick={onRollbackStorage}>回滚 JSON</button>
                </div>
              </div>
            </>
          )}
          {deletedJobs.length > 0 && (
            <div className="deleted-job-list">
              {deletedJobs.map(item => (
                <div className="deleted-job-item" key={item.id}>
                  <div>
                    <strong>{item.job.title || "未命名岗位"}</strong>
                    <span>{item.job.company || "未知公司"} · {item.deletedAt.slice(0, 19).replace("T", " ")}</span>
                  </div>
                  <button type="button" className="button-secondary button-secondary--sm" onClick={() => onRestoreDeletedJob(item.id)}>恢复</button>
                </div>
              ))}
            </div>
          )}
          {apiLogs.length > 0 && (
            <div className="maintenance-log-list">
              {apiLogs.map(log => (
                <div key={log.id} className="maintenance-log-item">
                  <span>{log.category}</span>
                  <p>{log.method} {log.url} · {log.statusCode} · {log.durationMs}ms</p>
                  <time>{log.time.slice(0, 19).replace("T", " ")}</time>
                </div>
              ))}
            </div>
          )}
          {maintenanceLogs.length > 0 && (
            <div className="maintenance-log-list">
              {maintenanceLogs.map(event => (
                <div key={event.id} className="maintenance-log-item">
                  <span>{event.category}</span>
                  <p>{event.message}</p>
                  <time>{event.time.slice(0, 19).replace("T", " ")}</time>
                </div>
              ))}
            </div>
          )}
          {maintenanceStatus && <p className="settings-status">{maintenanceStatus}</p>}
        </div>

        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
          <div className="page-kicker">本机数据</div>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 8px" }}>
            清除保存在本机浏览器里的流程状态、聊天记录和页面偏好，不会删除后端岗位池文件。
          </p>
          <div className="settings-row" style={{ alignItems: "center" }}>
            <label className="settings-label">浏览器数据</label>
            <button type="button" className="button-quiet button-danger" onClick={onClearLocalData}>清除本机流程数据</button>
          </div>
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

function releaseStatusLabel(status: ReleasePreflight["status"]): string {
  if (status === "ok") return "上线体检通过";
  if (status === "error") return "上线体检异常";
  return "上线体检需关注";
}

function pageLabel(page: string): string {
  const labels: Record<string, string> = {
    dashboard: "仪表盘",
    jobs: "岗位",
    diligence: "尽调",
    ranking: "排序",
    greeting: "打招呼",
    settings: "设置",
  };
  return labels[page] || page;
}

function migrationStatusLabel(status: StorageMigrationWizard["steps"][number]["status"]): string {
  if (status === "done") return "已完成";
  if (status === "available") return "可用";
  if (status === "blocked") return "等待前置";
  return "待处理";
}
