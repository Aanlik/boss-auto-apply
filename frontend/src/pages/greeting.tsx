import { useState, useEffect, useMemo } from "react";
import {
  listJobPool as poolJobs,
  analyzeJD,
  bossLoginStatus,
  checkGreetingSelectorHealth,
  aiOptimizeResume,
  controlGreetingSend,
  exportResumePdf,
  getGreetingAutoSendSettings,
  getGreetingAcceptancePlan,
  getGreetingAcceptanceRecords,
  getGreetingCandidates,
  getGreetingFollowups,
  getGreetingFinalConfirmation,
  getGreetingFrequencyProfiles,
  getGreetingProgress,
  getGreetingReplies,
  getGreetingStats,
  getGreetingSafetySummary,
  listResumeOptimizations,
	  tagJob,
	  confirmSendRecord,
	  updateSendRecord,
  getGreetingDrafts,
  getSendRecords,
  saveGreetingAcceptanceRecord,
  saveGreetingDrafts,
  generateGreeting,
  saveGreetingReply,
  saveGreetingAutoSendSettings,
  sendGreetingConfirmations,
  preflightGreetings,
  validateGreetingMessages,
  recommendPdfTemplate,
  previewResumePdf,
} from "../lib/api";
import type { BossLoginStatus, GreetingAcceptancePlan, GreetingAcceptanceRecord, GreetingCandidateResponse, GreetingFinalConfirmation, GreetingFollowups, GreetingFrequencyProfile, GreetingPreflight, GreetingProgress, GreetingReplyRecord, GreetingSafetySummary, GreetingSelectorHealth, GreetingSendResponse, GreetingStats, GreetingValidationResult, JobPosting } from "../lib/types";
import { useWorkflowState, useWorkflowDispatch, actions } from "../lib/store";
import { resolveAutoSendAction, resolveGreetingBatchActions } from "../lib/greetingActions";
import ChatPanel from "../components/ChatPanel";
import { EmptyState, ErrorBanner } from "../components/SharedUI";

type GreetingBatchFilter =
  | "selected"
  | "ready"
  | "ungreeted"
  | "missing_greeting"
  | "missing_jd"
  | "recommended"
  | "safe"
  | "all";

const GREETING_BATCH_FILTERS: Array<{ key: GreetingBatchFilter; label: string }> = [
  { key: "selected", label: "岗位页已选" },
  { key: "ready", label: "可直接发送" },
  { key: "ungreeted", label: "未打招呼" },
  { key: "missing_greeting", label: "缺少话术" },
  { key: "missing_jd", label: "缺少 JD" },
  { key: "recommended", label: "决策推荐" },
  { key: "safe", label: "低风险" },
  { key: "all", label: "全部岗位" },
];

function maskGreetingSensitiveText(text: string) {
  return text
    .replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, value => `${value.slice(0, 3)}****${value.slice(-4)}`)
    .replace(/(邮箱\s*[:：]\s*)([^\s|，。；;]+)/gi, "$1***")
    .replace(/([A-Za-z0-9._%+-]{1,2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/g, "$1***$2");
}

function formatSafetyCheckMessage(check: GreetingSafetySummary["checks"][number]) {
  return check.message;
}

export default function GreetingPage({ visible = true }: { visible?: boolean }) {
  const { greetingJobIds, resumeProfile, jdAnalyses, optimizations, greetingTexts, chatMessages } = useWorkflowState();
  const dispatch = useWorkflowDispatch();

  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [loading, setLoading] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [greetedStatus, setGreetedStatus] = useState<Record<string, boolean>>({});
  const [customTags, setCustomTags] = useState<Record<string, string[]>>({});
  const [tagInputs, setTagInputs] = useState<Record<string, string>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [pdfTemplate, setPdfTemplate] = useState<"modern" | "classic" | "ats">("modern");
  const [pdfDensity] = useState("balanced");
  const [pdfTemplateReason, setPdfTemplateReason] = useState("");
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState("");
  const [pdfPreviewTitle, setPdfPreviewTitle] = useState("");
  const [candidateResult, setCandidateResult] = useState<GreetingCandidateResponse | null>(null);
  const [sendResult, setSendResult] = useState<GreetingSendResponse | null>(null);
  const [validationResults, setValidationResults] = useState<Record<string, GreetingValidationResult>>({});
  const [workbenchLoading, setWorkbenchLoading] = useState("");
  const [autoDailyLimit, setAutoDailyLimit] = useState(15);
  const [autoIntervalSeconds, setAutoIntervalSeconds] = useState(8);
  const [autoSendEnabled, setAutoSendEnabled] = useState(false);
  const [autoSendProfile, setAutoSendProfile] = useState("standard");
  const [grayModeEnabled, setGrayModeEnabled] = useState(true);
  const [frequencyProfiles, setFrequencyProfiles] = useState<GreetingFrequencyProfile[]>([]);
  const [preflightResult, setPreflightResult] = useState<GreetingPreflight | null>(null);
  const [progress, setProgress] = useState<GreetingProgress | null>(null);
  const [greetingStats, setGreetingStats] = useState<GreetingStats | null>(null);
  const [safetySummary, setSafetySummary] = useState<GreetingSafetySummary | null>(null);
  const [selectorHealth, setSelectorHealth] = useState<GreetingSelectorHealth | null>(null);
  const [acceptancePlan, setAcceptancePlan] = useState<GreetingAcceptancePlan | null>(null);
  const [acceptanceRecords, setAcceptanceRecords] = useState<GreetingAcceptanceRecord[]>([]);
  const [replyRecords, setReplyRecords] = useState<GreetingReplyRecord[]>([]);
  const [followups, setFollowups] = useState<GreetingFollowups | null>(null);
  const [finalConfirmation, setFinalConfirmation] = useState<GreetingFinalConfirmation | null>(null);
  const [greetingFilter, setGreetingFilter] = useState<GreetingBatchFilter>("selected");
  const [greetingSelectedIds, setGreetingSelectedIds] = useState<string[]>([]);
  const [bossLogin, setBossLogin] = useState<BossLoginStatus | null>(null);
  const [revealedGreetingIds, setRevealedGreetingIds] = useState<string[]>([]);

  async function refreshPageData() {
    setWorkbenchLoading("刷新中...");
    setError("");
    try {
      const [jobsResult, draftsResult, recordsResult, optimizationsResult, settingsResult, profilesResult, progressResult, statsResult, safetyResult, followupResult, acceptanceResult, repliesResult, loginResult] = await Promise.all([
        poolJobs(), getGreetingDrafts(), getSendRecords(), listResumeOptimizations(), getGreetingAutoSendSettings(), getGreetingFrequencyProfiles(), getGreetingProgress(), getGreetingStats(), getGreetingSafetySummary(), getGreetingFollowups(), getGreetingAcceptanceRecords(), getGreetingReplies(), bossLoginStatus(false),
      ]);
      const filtered = (jobsResult.jobs || []).filter(job => greetingJobIds.includes(job.id));
      setJobs(filtered);
      setGreetedStatus(Object.fromEntries(recordsResult.records?.filter(record => record.status === "sent").map(record => [record.jobId, true]) || []));
      setCustomTags(Object.fromEntries(filtered.filter(job => job.tags?.length).map(job => [job.id, job.tags || []])));
      if (draftsResult.greetings) dispatch(actions.setGreetingTexts({ ...greetingTexts, ...draftsResult.greetings }));
      if (optimizationsResult.optimizations) dispatch(actions.setOptimizations({ ...optimizations, ...optimizationsResult.optimizations }));
      setAutoSendEnabled(!!settingsResult.settings.auto_send_enabled);
      setAutoSendProfile(settingsResult.settings.profile);
      setGrayModeEnabled(settingsResult.settings.gray_mode_enabled !== false);
      setAutoDailyLimit(settingsResult.settings.daily_limit);
      setAutoIntervalSeconds(settingsResult.settings.send_interval_seconds);
      setFrequencyProfiles(profilesResult.profiles || settingsResult.profiles || []);
      setProgress(progressResult); setGreetingStats(statsResult); setSafetySummary(safetyResult); setFollowups(followupResult);
      setAcceptanceRecords(acceptanceResult.records || []); setReplyRecords(repliesResult.records || []); setBossLogin(loginResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "刷新打招呼数据失败");
    } finally {
      setWorkbenchLoading("");
    }
  }

  useEffect(() => () => {
    if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl);
  }, [pdfPreviewUrl]);

  useEffect(() => {
    if (visible) void refreshPageData();
  }, [visible, greetingJobIds]);

  useEffect(() => {
    const validIds = new Set(jobs.map(job => job.id));
    const selected = greetingJobIds.filter(id => validIds.has(id));
    console.info("[greeting-selection] 打招呼页恢复目标", { imported: greetingJobIds.length, available: jobs.length, selected: selected.length, jobIds: selected });
    setGreetingSelectedIds(selected);
  }, [jobs, greetingJobIds]);

  useEffect(() => {
    if (!visible) return;
    const timer = window.setInterval(() => {
      getGreetingProgress().then(setProgress).catch(() => {});
    }, 5000);
    return () => window.clearInterval(timer);
  }, [visible]);

  // 确保 JD 分析存在 — 优先从 store 读取，没有则请求
  async function ensureJDAnalysis(job: JobPosting) {
    if (jdAnalyses[job.id]) return jdAnalyses[job.id];
    setLoading(prev => ({ ...prev, [job.id + "-jd"]: "分析中…" }));
    try {
      const data = await analyzeJD({ job_id: job.id, title: job.title, company: job.company, jd_text: job.jd_text });
      dispatch(actions.setJdAnalyses({ ...jdAnalyses, [job.id]: data }));
      return data;
    } catch { return null; }
    finally { setLoading(prev => ({ ...prev, [job.id + "-jd"]: "" })); }
  }

  async function onOptimize(job: JobPosting) {
    if (!resumeProfile) return;
    setLoading(prev => ({ ...prev, [job.id + "-opt"]: "生成中…" })); setError("");
    try {
      const jdA = await ensureJDAnalysis(job);
      const data = await aiOptimizeResume(resumeProfile, { id: job.id, title: job.title, company: job.company, jd_text: job.jd_text }, null, jdA || undefined);
      dispatch(actions.setOptimizations({ ...optimizations, [job.id]: data }));
    } catch (err) { setError(err instanceof Error ? err.message : "优化失败"); }
    finally { setLoading(prev => ({ ...prev, [job.id + "-opt"]: "" })); }
  }

	  async function onGenerateGreeting(job: JobPosting) {
	    setLoading(prev => ({ ...prev, [job.id + "-greet"]: "生成中…" }));
	    setError("");
	    try {
	      const jdA = await ensureJDAnalysis(job);
	      if (!resumeProfile) { setError("请先上传简历"); return; }
	      const generated = await generateGreeting({ job_id: job.id, resume: resumeProfile, jd_analysis: jdA });
	      const next = { ...greetingTexts, [job.id]: generated.message };
	      dispatch(actions.setGreetingTexts(next));
	      await saveGreetingDrafts(next);
	    } catch (err) { setError(err instanceof Error ? err.message : "生成失败"); }
	    finally { setLoading(prev => ({ ...prev, [job.id + "-greet"]: "" })); }
	  }

	  // —— 批量操作 ——
	  async function batchGenerateGreetings() {
	    const targets = greetingTargetIds.length > 0 ? greetingTargetIds : filteredGreetingJobs.map(j => j.id);
	    if (targets.length === 0) { setError("没有可生成话术的岗位"); return; }
	    setWorkbenchLoading(`生成中 0/${targets.length}…`);
	    setError("");
	    try {
	      const next = { ...greetingTexts };
	      for (let i = 0; i < targets.length; i++) {
	        const job = jobs.find(j => j.id === targets[i]);
	        if (!job) continue;
	        setWorkbenchLoading(`生成中 ${i + 1}/${targets.length}…`);
	        const jdA = await ensureJDAnalysis(job);
	        if (!resumeProfile) { setError("请先上传简历"); return; }
	        const generated = await generateGreeting({ job_id: job.id, resume: resumeProfile, jd_analysis: jdA });
	        next[targets[i]] = generated.message;
	      }
	      dispatch(actions.setGreetingTexts(next));
	      await saveGreetingDrafts(next);
	    } catch (err) { setError(err instanceof Error ? err.message : "批量生成失败"); }
	    finally { setWorkbenchLoading(""); }
	  }

	  async function batchRegenerateGreetings() {
	    const targets = greetingTargetIds.filter(id => greetingTexts[id]);
	    if (targets.length === 0) { setError("没有需要重新生成的话术"); return; }
	    const next = { ...greetingTexts };
	    targets.forEach(id => delete next[id]);
	    dispatch(actions.setGreetingTexts(next));
	    await batchGenerateGreetings();
	  }

	  function copyAllGreetings() {
	    const targets = greetingTargetIds.length > 0 ? greetingTargetIds : filteredGreetingJobs.map(j => j.id);
	    const lines = targets
      .map(id => { const job = jobs.find(j => j.id === id); const msg = greetingTexts[id]; return job && msg ? `${job.company} · ${job.title}：\n${msg}` : null; })
	      .filter(Boolean);
	    if (lines.length === 0) { setError("没有可复制的话术"); return; }
    navigator.clipboard.writeText(lines.join("\n\n")).then(() => { setCopiedId("all"); setTimeout(() => setCopiedId(null), 2000); }).catch(() => {});
	  }

	  async function batchOptimizeResume() {
	    const targets = requireGreetingTargets("AI 优化简历");
	    if (!targets) return;
	    if (!resumeProfile) { setError("请先上传简历"); return; }
	    setWorkbenchLoading(`AI 优化中 0/${targets.length}…`);
	    setError("");
	    try {
        const nextOptimizations = { ...optimizations };
	      for (let i = 0; i < targets.length; i++) {
	        const job = jobs.find(j => j.id === targets[i]);
	        if (!job) continue;
	        setWorkbenchLoading(`AI 优化中 ${i + 1}/${targets.length}…`);
	        const jdA = await ensureJDAnalysis(job);
	        const data = await aiOptimizeResume(resumeProfile, { id: job.id, title: job.title, company: job.company, jd_text: job.jd_text }, null, jdA || undefined);
          nextOptimizations[targets[i]] = data;
	        dispatch(actions.setOptimizations({ ...nextOptimizations }));
	      }
	    } catch (err) { setError(err instanceof Error ? err.message : "AI 优化失败"); }
	    finally { setWorkbenchLoading(""); }
	  }

	  async function markGreeted(jobId: string) {
	    const oldVal = !!greetedStatus[jobId];
	    const newVal = !oldVal;
	    setGreetedStatus(prev => ({ ...prev, [jobId]: newVal }));
	    try {
	      await tagJob(jobId, { greeted: newVal });
	      if (newVal) {
          await confirmSendRecord(jobId);
          dispatch(actions.setGreetingSelection(greetingJobIds.filter(id => id !== jobId)));
        }
	      else await updateSendRecord(jobId, "pending", "人工撤销已打招呼");
	    } catch (err) {
	      setGreetedStatus(prev => ({ ...prev, [jobId]: oldVal }));
	      setError(err instanceof Error ? err.message : "标记失败");
	    }
	  }

  async function addCustomTag(jobId: string, tag: string) {
    if (!tag.trim()) return;
    const current = customTags[jobId] || []; const newTags = [...current, tag.trim()];
    setCustomTags(prev => ({ ...prev, [jobId]: newTags })); setTagInputs(prev => ({ ...prev, [jobId]: "" }));
	    try { await tagJob(jobId, { tags: newTags }); }
	    catch (err) {
	      setCustomTags(prev => ({ ...prev, [jobId]: current }));
	      setError(err instanceof Error ? err.message : "标签保存失败");
	    }
	  }

  function copyGreeting(text: string, jobId: string) {
    navigator.clipboard.writeText(text).then(() => { setCopiedId(jobId); setTimeout(() => setCopiedId(null), 2000); }).catch(() => {});
  }

  const selectedJobIdSet = useMemo(() => new Set(greetingJobIds), [greetingJobIds]);

  function hasJobJD(job: JobPosting) {
    return Boolean((job.jd_text || "").trim() || jdAnalyses[job.id]);
  }

  function isGreetingSafe(job: JobPosting) {
    return job.lifecycle_status !== "blacklisted" && job.decision_status !== "risky";
  }

  function isGreetingReady(job: JobPosting) {
    return isGreetingSafe(job) && !greetedStatus[job.id] && hasJobJD(job) && Boolean((greetingTexts[job.id] || "").trim());
  }

  const filteredGreetingJobs = useMemo(() => jobs.filter(job => {
    if (greetingFilter === "selected") return selectedJobIdSet.has(job.id);
    if (greetingFilter === "ready") return isGreetingReady(job);
    if (greetingFilter === "ungreeted") return !greetedStatus[job.id];
    if (greetingFilter === "missing_greeting") return !(greetingTexts[job.id] || "").trim();
    if (greetingFilter === "missing_jd") return !hasJobJD(job);
    if (greetingFilter === "recommended") return job.decision_status === "recommended";
    if (greetingFilter === "safe") return isGreetingSafe(job);
    return true;
  }), [jobs, greetingFilter, selectedJobIdSet, greetedStatus, greetingTexts, jdAnalyses]);

  const greetingTargetIds = useMemo(() => {
    const validIds = new Set(jobs.map(job => job.id));
    return greetingSelectedIds.filter(id => validIds.has(id));
  }, [greetingSelectedIds, jobs]);

  const greetingTargetSet = useMemo(() => new Set(greetingTargetIds), [greetingTargetIds]);
  const visibleSelectedCount = filteredGreetingJobs.filter(job => greetingTargetSet.has(job.id)).length;
  const currentFilterLabel = GREETING_BATCH_FILTERS.find(item => item.key === greetingFilter)?.label || "当前范围";
  const batchActions = resolveGreetingBatchActions({
    selectedCount: greetingTargetIds.length,
    hasResumeProfile: Boolean(resumeProfile),
    isBusy: Boolean(workbenchLoading),
  });
  const autoSendAction = resolveAutoSendAction({
    autoSendEnabled,
    loggedIn: Boolean(bossLogin?.logged_in),
    selectedCount: greetingTargetIds.length,
    isBusy: Boolean(workbenchLoading),
    safetyBlocked: safetySummary?.status === "blocked",
    dailyLimit: safetySummary?.summary.dailyLimit ?? autoDailyLimit,
    sentToday: safetySummary?.summary.sentToday ?? 0,
    grayBatchAllowed: safetySummary?.summary.grayMode?.batchAllowed ?? false,
  });
  const isAutoSendReady = autoSendAction.enabled;
  const selectedFrequencyProfile = useMemo(() => {
    const profile = frequencyProfiles.find(item => item.key === autoSendProfile);
    return profile && profile.dailyLimit === autoDailyLimit && profile.intervalSeconds === autoIntervalSeconds
      ? autoSendProfile
      : "";
  }, [frequencyProfiles, autoSendProfile, autoDailyLimit, autoIntervalSeconds]);

  function requireGreetingTargets(actionLabel = "批量操作") {
    if (greetingTargetIds.length === 0) {
      setError(`请先选择本次${actionLabel}的岗位`);
      return null;
    }
    return greetingTargetIds;
  }

  function selectVisibleGreetingJobs() {
    setGreetingSelectedIds(prev => {
      const next = new Set(prev);
      filteredGreetingJobs.forEach(job => next.add(job.id));
      return Array.from(next);
    });
  }

  function unselectVisibleGreetingJobs() {
    const visibleIds = new Set(filteredGreetingJobs.map(job => job.id));
    setGreetingSelectedIds(prev => prev.filter(id => !visibleIds.has(id)));
  }

  function invertVisibleGreetingJobs() {
    setGreetingSelectedIds(prev => {
      const next = new Set(prev);
      filteredGreetingJobs.forEach(job => {
        if (next.has(job.id)) next.delete(job.id);
        else next.add(job.id);
      });
      return Array.from(next);
    });
  }

  function toggleGreetingJob(jobId: string, checked: boolean) {
    setGreetingSelectedIds(prev => checked ? Array.from(new Set([...prev, jobId])) : prev.filter(id => id !== jobId));
  }

  async function refreshGreetingCandidates(idsOverride?: string[]) {
    const targetIds = idsOverride || requireGreetingTargets("筛选候选");
    if (!targetIds) return;
    setWorkbenchLoading("候选筛选中…");
    setError("");
    try {
      setCandidateResult(await getGreetingCandidates(targetIds));
    } catch (err) {
      setError(err instanceof Error ? err.message : "候选筛选失败");
    } finally {
      setWorkbenchLoading("");
    }
  }

  async function validateCurrentGreetings() {
    const targetIds = requireGreetingTargets("校验话术");
    if (!targetIds) return;
    const items = targetIds
      .map(jobId => ({ job_id: jobId, message: greetingTexts[jobId] || "" }))
      .filter(item => item.message.trim());
    if (items.length === 0) {
      setError("暂无可校验的招呼语，请先生成草稿");
      return;
    }
    setWorkbenchLoading("校验中…");
    setError("");
    try {
      const result = await validateGreetingMessages(items);
      setValidationResults(Object.fromEntries(result.results.map(item => [item.jobId, item])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "校验失败");
    } finally {
      setWorkbenchLoading("");
    }
  }

  function selectedGreetingMessages(targetIds = greetingTargetIds) {
    return Object.fromEntries(
      targetIds
        .map(jobId => [jobId, greetingTexts[jobId] || ""] as const)
        .filter(([, message]) => message.trim())
    );
  }

  async function toggleAutoSendEnabled(nextValue: boolean) {
    setAutoSendEnabled(nextValue);
    try {
      const saved = await saveGreetingAutoSendSettings({ auto_send_enabled: nextValue, profile: autoSendProfile, gray_mode_enabled: grayModeEnabled });
      setAutoSendEnabled(!!saved.settings.auto_send_enabled);
      setAutoSendProfile(saved.settings.profile);
      setGrayModeEnabled(saved.settings.gray_mode_enabled !== false);
      setAutoDailyLimit(saved.settings.daily_limit);
      setAutoIntervalSeconds(saved.settings.send_interval_seconds);
      getGreetingSafetySummary().then(setSafetySummary).catch(() => {});
    } catch (err) {
      setAutoSendEnabled(!nextValue);
      setError(err instanceof Error ? err.message : "自动发送设置保存失败");
    }
  }

  async function toggleGrayMode(nextValue: boolean) {
    setGrayModeEnabled(nextValue);
    try {
      const saved = await saveGreetingAutoSendSettings({
        auto_send_enabled: autoSendEnabled,
        profile: autoSendProfile,
        gray_mode_enabled: nextValue,
        gray_first_success_required: true,
      });
      setGrayModeEnabled(saved.settings.gray_mode_enabled !== false);
      setAutoSendProfile(saved.settings.profile);
      setAutoDailyLimit(saved.settings.daily_limit);
      setAutoIntervalSeconds(saved.settings.send_interval_seconds);
      getGreetingSafetySummary().then(setSafetySummary).catch(() => {});
    } catch (err) {
      setGrayModeEnabled(!nextValue);
      setError(err instanceof Error ? err.message : "灰度模式保存失败");
    }
  }

  function applyFrequencyProfile(profile: GreetingFrequencyProfile) {
    setAutoIntervalSeconds(profile.intervalSeconds);
    setAutoDailyLimit(profile.dailyLimit);
    setAutoSendProfile(profile.key);
    saveGreetingAutoSendSettings({
      auto_send_enabled: autoSendEnabled,
      profile: profile.key,
      gray_mode_enabled: grayModeEnabled,
      daily_limit: profile.dailyLimit,
      send_interval_seconds: profile.intervalSeconds,
    }).then(saved => {
      setAutoSendProfile(saved.settings.profile);
      setAutoDailyLimit(saved.settings.daily_limit);
      setAutoIntervalSeconds(saved.settings.send_interval_seconds);
      getGreetingSafetySummary().then(setSafetySummary).catch(() => {});
    }).catch(() => {});
  }

  async function saveFrequencySettings(dailyLimit: number, intervalSeconds: number) {
    try {
      const saved = await saveGreetingAutoSendSettings({
        auto_send_enabled: autoSendEnabled,
        profile: autoSendProfile,
        gray_mode_enabled: grayModeEnabled,
        daily_limit: dailyLimit,
        send_interval_seconds: intervalSeconds,
      });
      setAutoDailyLimit(saved.settings.daily_limit);
      setAutoIntervalSeconds(saved.settings.send_interval_seconds);
      setAutoSendProfile(saved.settings.profile);
      getGreetingSafetySummary().then(setSafetySummary).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送频率保存失败");
    }
  }

  async function runPreflight() {
    const targetIds = requireGreetingTargets("预检");
    if (!targetIds) return;
    const messages = selectedGreetingMessages(targetIds);
    if (Object.keys(messages).length === 0) {
      setError("暂无可预检的招呼语，请先生成草稿");
      return;
    }
    setWorkbenchLoading("预检中…");
    setError("");
    try {
      const login = await bossLoginStatus(true);
      setBossLogin(login);
      if (!login.logged_in) {
        setError(login.message || "请先验证 BOSS 登录");
        return;
      }
      setPreflightResult(await preflightGreetings({ job_ids: targetIds, messages, mode: autoSendEnabled ? "browser_auto" : "manual_confirm" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送前预检失败");
    } finally {
      setWorkbenchLoading("");
    }
  }

  async function runSelectorHealth() {
    const firstJobId = greetingTargetIds[0] || filteredGreetingJobs[0]?.id;
    if (!firstJobId) {
      setError("请先选择一个岗位用于检测页面可用性");
      return;
    }
    setWorkbenchLoading("检测页面中…");
    setError("");
    try {
      setSelectorHealth(await checkGreetingSelectorHealth(firstJobId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "选择器健康检查失败");
    } finally {
      setWorkbenchLoading("");
    }
  }

  async function loadAcceptancePlan() {
    const firstJobId = greetingTargetIds[0] || filteredGreetingJobs[0]?.id;
    if (!firstJobId) {
      setError("请先选择一个岗位用于生成验收步骤");
      return;
    }
    try {
      setAcceptancePlan(await getGreetingAcceptancePlan(firstJobId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "人工验收步骤加载失败");
    }
  }

  async function recordAcceptance(job: JobPosting) {
    try {
      const result = await saveGreetingAcceptanceRecord({
        job_id: job.id,
        result: "passed",
        operator: "本机用户",
        note: "已按人工验收步骤检查 BOSS 页面和发送结果",
        checks: [
          { key: "open_job", status: "passed", note: "岗位详情已打开" },
          { key: "confirm_send", status: "passed", note: "发送结果已人工确认" },
        ],
      });
      setAcceptanceRecords(prev => [result.record, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "验收记录保存失败");
    }
  }

  async function recordReply(job: JobPosting) {
    const content = window.prompt("记录 HR 回复内容或摘要");
    if (!content?.trim()) return;
    const replyType = window.confirm("这次回复是否偏积极？") ? "positive" : "neutral";
    try {
      const result = await saveGreetingReply({
        job_id: job.id,
        reply_type: replyType,
        content: content.trim(),
        next_action: replyType === "positive" ? "准备下一轮沟通或面试时间" : "继续观察并择机跟进",
      });
      setReplyRecords(prev => [result.record, ...prev]);
      getGreetingStats().then(setGreetingStats).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "回复记录保存失败");
    }
  }

  async function updateControl(action: "pause" | "resume" | "stop") {
    try {
      const result = await controlGreetingSend(action);
      setProgress(prev => ({ control: result.control, task: prev?.task || null, recent: prev?.recent || [] }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送控制失败");
    }
  }

  async function sendSelectedGreetings(mode: "manual_confirm" | "browser_auto") {
    const targetIds = requireGreetingTargets(mode === "browser_auto" ? "自动发送" : "人工确认");
    if (!targetIds) return;
    console.info("[greeting-selection] 提交发送目标", { mode, count: targetIds.length, jobIds: targetIds });
    const messages = selectedGreetingMessages(targetIds);
    if (Object.keys(messages).length === 0) {
      setError("暂无可确认发送的招呼语，请先生成草稿");
      return;
    }
    setError("");
    try {
      const confirmation = await getGreetingFinalConfirmation({
        job_ids: targetIds,
        messages,
        mode,
        daily_limit: autoDailyLimit,
      });
      setFinalConfirmation(confirmation);
      if (confirmation.status === "blocked") {
        setError(confirmation.riskItems.join("；") || "当前批次暂不适合发送");
        return;
      }
      const riskCopy = confirmation.riskItems.length ? `\n风险项：${confirmation.riskItems.join("；")}` : "";
      const linkCopy = confirmation.links.slice(0, 5).join("\n");
      const ok = window.confirm(`${confirmation.confirmText}${riskCopy}\n\n将打开链接：\n${linkCopy || "无外部链接"}`);
      if (!ok) return;
      setWorkbenchLoading(mode === "browser_auto" ? "自动发送中…" : "确认发送中…");
      const result = await sendGreetingConfirmations({
        job_ids: targetIds,
        messages,
        confirm: true,
        mode,
        daily_limit: autoDailyLimit,
        send_interval_seconds: mode === "browser_auto" ? autoIntervalSeconds : 0,
        stop_on_blocked: true,
      });
      setSendResult(result);
      getGreetingStats().then(setGreetingStats).catch(() => {});
      getGreetingProgress().then(setProgress).catch(() => {});
      getGreetingSafetySummary().then(setSafetySummary).catch(() => {});
      if (result.records.length > 0) {
        const sentIds = new Set(result.records.filter(record => record.status === "sent").map(record => record.jobId));
        if (sentIds.size > 0) {
          dispatch(actions.setGreetingSelection(greetingJobIds.filter(id => !sentIds.has(id))));
        }
        setGreetedStatus(prev => {
          const next = { ...prev };
          result.records.forEach(record => {
            if (record.status === "sent") next[record.jobId] = true;
          });
          return next;
        });
      }
      await refreshGreetingCandidates(targetIds);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setWorkbenchLoading("");
    }
  }

  async function confirmSelectedGreetingsSent() {
    await sendSelectedGreetings("manual_confirm");
  }

  async function autoSendSelectedGreetings() {
    if (!autoSendAction.enabled) {
      setError(autoSendAction.reason);
      return;
    }
    await sendSelectedGreetings("browser_auto");
  }

  async function onExportPdf(job: JobPosting) {
    const opt = optimizations[job.id]; if (!opt || !resumeProfile) return;
    setLoading(prev => ({ ...prev, [job.id + "-pdf"]: "导出中…" }));
    try { await exportResumePdf({ profile: resumeProfile, optimization: opt, company: job.company, job_title: resumeProfile.title || job.title, template: pdfTemplate, density: pdfDensity }); }
    catch (err) { setError(err instanceof Error ? err.message : "导出失败"); }
    finally { setLoading(prev => ({ ...prev, [job.id + "-pdf"]: "" })); }
  }

  async function onRecommendTemplate(job: JobPosting) {
    try {
      const r = await recommendPdfTemplate({ job_title: job.title, profile: resumeProfile });
      setPdfTemplate(r.template);
      setPdfTemplateReason(r.reason);
    } catch (err) {
      setError(err instanceof Error ? err.message : "模板推荐失败");
    }
  }

  async function onPreviewPdf(job: JobPosting) {
    const opt = optimizations[job.id];
    if (!opt || !resumeProfile) return;
    setLoading(prev => ({ ...prev, [job.id + "-preview"]: "预览生成中…" }));
    try {
      if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl);
      const url = await previewResumePdf({
        profile: resumeProfile,
        optimization: opt,
        company: job.company,
        job_title: resumeProfile.title || job.title,
        template: pdfTemplate,
        density: pdfDensity,
      });
      setPdfPreviewUrl(url);
      setPdfPreviewTitle(`${job.company} · ${job.title}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "预览失败");
    } finally {
      setLoading(prev => ({ ...prev, [job.id + "-preview"]: "" }));
    }
  }

  const bossUrl = (job: JobPosting) => job.source_url || `https://www.zhipin.com/web/geek/job?query=${encodeURIComponent(job.title)}&city=100010000`;

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">智能打招呼</p>
          <h2 className="page-title">打招呼语与简历修订</h2>
          <p className="page-copy">根据岗位 JD 生成定制打招呼语，AI 逐岗位优化简历并支持导出。</p>
        </div>
        <button type="button" className="button-secondary" aria-label="刷新打招呼数据" title="刷新打招呼数据" disabled={!!workbenchLoading} onClick={() => void refreshPageData()}>
          {workbenchLoading === "刷新中..." ? "刷新中..." : "刷新数据"}
        </button>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}
      {pdfPreviewUrl && (
        <div className="pdf-preview-overlay" role="presentation" onClick={() => setPdfPreviewUrl("")}>
          <button type="button" className="pdf-preview-close" onClick={() => setPdfPreviewUrl("")} aria-label="关闭 PDF 简历预览">关闭</button>
          <div className="pdf-preview-dialog" role="dialog" aria-label="PDF 简历预览" onClick={e => e.stopPropagation()} onKeyDown={e => { if (e.key === "Escape") setPdfPreviewUrl(""); }} tabIndex={-1}>
            <div className="pdf-preview-dialog__header">
              <strong>PDF 简历预览 · {pdfPreviewTitle}</strong>
            </div>
            <iframe title="PDF 简历预览" src={pdfPreviewUrl} />
          </div>
        </div>
      )}

      {jobs.length === 0 && (
        <div className="panel panel-strong"><div className="panel-inner"><EmptyState icon="👋" title="尚未从排序页选择岗位" desc="请先在「排序」页面勾选需要联系的岗位，再进入打招呼。" /></div></div>
      )}

      {jobs.length > 0 && (
        <div className="panel panel-strong greeting-workbench">
          <div className="panel-inner">
            <div className="page-section__top">
              <div>
                <p className="page-kicker">boss 求职助手</p>
                <h3 className="section-title">先生成、校验和审核，再由你决定是否发送</h3>
                <p className="text-muted">支持人工确认和真实自动发送；真实发送需先打开总开关并通过预检。</p>
              </div>
            </div>

            <div className="greeting-action-grid">
              <section className="greeting-action-group greeting-action-group--primary" aria-label="准备话术">
                <span className="greeting-action-group__label">准备话术</span>
                <div className="toolbar-row toolbar-row--wrap">
                  <button type="button" className="button-secondary" disabled={!!workbenchLoading} onClick={() => refreshGreetingCandidates()}>
                    筛选候选
                  </button>
                  <button type="button" className="button-primary" disabled={!!workbenchLoading} onClick={batchGenerateGreetings}>
                    {workbenchLoading || "生成话术"}
                  </button>
                  <button type="button" className="button-secondary" disabled={!!workbenchLoading} onClick={copyAllGreetings}>
                    {copiedId === "all" ? "已复制" : "复制话术"}
                  </button>
                </div>
              </section>
              <section className="greeting-action-group" aria-label="发送">
                <span className="greeting-action-group__label">发送</span>
                <div className="toolbar-row toolbar-row--wrap">
                  <button type="button" className="button-secondary" disabled={!!workbenchLoading} onClick={confirmSelectedGreetingsSent}>
                    确认已人工发送
                  </button>
                  <button type="button" className="button-primary" disabled={!autoSendAction.enabled} title={autoSendAction.reason} onClick={autoSendSelectedGreetings}>
                    自动打开 BOSS 发送
                  </button>
                  {!autoSendAction.enabled && (
                    <button type="button" className="button-secondary" disabled={!!workbenchLoading} onClick={runPreflight}>
                      发送前预检
                    </button>
                  )}
                </div>
              </section>
              <details className="greeting-action-group greeting-action-group--details">
                <summary>更多与安全</summary>
                <div className="greeting-more-actions">
                  <button type="button" className="button-secondary" disabled={!!workbenchLoading} onClick={validateCurrentGreetings}>校验当前话术</button>
                  <button type="button" className="button-secondary" disabled={!!workbenchLoading} onClick={batchRegenerateGreetings}>重新生成</button>
                  <button type="button" className="button-secondary" disabled={!batchActions.canOptimizeResume} title={batchActions.optimizeResumeTitle} onClick={batchOptimizeResume}>AI 优化简历</button>
                  <button type="button" className="button-secondary" disabled={!!workbenchLoading} onClick={runPreflight}>发送前预检</button>
                  <button type="button" className="button-secondary" disabled={!!workbenchLoading} onClick={() => getGreetingSafetySummary().then(setSafetySummary).catch(() => {})}>刷新安全阈值</button>
                  <button type="button" className="button-secondary" disabled={!!workbenchLoading} onClick={runSelectorHealth}>检测页面可用性</button>
                  <button type="button" className="button-secondary" onClick={loadAcceptancePlan}>人工验收步骤</button>
                  <button type="button" className="button-quiet" onClick={() => updateControl("pause")}>暂停</button>
                  <button type="button" className="button-quiet" onClick={() => updateControl("resume")}>继续</button>
                  <button type="button" className="button-quiet button-danger" onClick={() => updateControl("stop")}>终止</button>
                  <span>控制状态：{progress?.control.state === "paused" ? "已暂停" : progress?.control.state === "stopped" ? "已终止" : "运行中"}</span>
                  {progress?.task && <span>当前任务：{progress.task.done}/{progress.task.total} · {progress.task.message || progress.task.status}</span>}
                </div>
              </details>
            </div>

            <div className="greeting-selection-panel">
              <div className="greeting-selection-panel__main">
                <label className="greeting-selection-filter">
                  <span>本次批量范围</span>
                  <select
                    className="form-input form-input--inline"
                    value={greetingFilter}
                    onChange={event => setGreetingFilter(event.target.value as GreetingBatchFilter)}
                  >
                    {GREETING_BATCH_FILTERS.map(filter => (
                      <option key={filter.key} value={filter.key}>{filter.label}</option>
                    ))}
                  </select>
                </label>
                <div className="greeting-selection-summary">
                  <span>当前显示 <strong>{filteredGreetingJobs.length}</strong></span>
                  <span>本次已选 <strong>{greetingTargetIds.length}</strong></span>
                  <span>当前范围已选 <strong>{visibleSelectedCount}</strong></span>
                </div>
              </div>
            </div>

            <div className="greeting-auto-controls">
              <label className="greeting-toggle">
                <input
                  type="checkbox"
                  checked={autoSendEnabled}
                  onChange={event => toggleAutoSendEnabled(event.target.checked)}
                />
                <span>允许真实自动发送</span>
              </label>
              <label className="greeting-toggle">
                <input
                  type="checkbox"
                  checked={grayModeEnabled}
                  onChange={event => toggleGrayMode(event.target.checked)}
                />
                <span>灰度模式</span>
              </label>
              <label>
                <span>发送间隔(秒)</span>
                <input
                  className="form-input form-input--inline"
                  type="number"
                  min={3}
                  max={30}
                  value={autoIntervalSeconds}
                  onChange={event => setAutoIntervalSeconds(Math.max(3, Math.min(30, Number(event.target.value) || 3)))}
                  onBlur={() => saveFrequencySettings(autoDailyLimit, autoIntervalSeconds)}
                />
              </label>
              <label>
                <span>今日上限</span>
                <input
                  className="form-input form-input--inline"
                  type="number"
                  min={1}
                  max={100}
                  value={autoDailyLimit}
                  onChange={event => setAutoDailyLimit(Math.max(1, Math.min(100, Number(event.target.value) || 1)))}
                  onBlur={() => saveFrequencySettings(autoDailyLimit, autoIntervalSeconds)}
                />
              </label>
              <label>
                <span>频率模板</span>
                <select
                  className="form-input form-input--inline"
                  onChange={event => {
                    const profile = frequencyProfiles.find(item => item.key === event.target.value);
                    if (profile) applyFrequencyProfile(profile);
                  }}
                  value={selectedFrequencyProfile}
                >
                  <option value="" disabled>选择模板</option>
                  {frequencyProfiles.map(profile => (
                    <option key={profile.key} value={profile.key}>{profile.label}</option>
                  ))}
                </select>
              </label>
              <small>{grayModeEnabled ? "灰度模式会要求先成功发送 1 个岗位，再开放批量真实发送。" : "遇到登录失效、验证码或风控会停止剩余岗位。"}</small>
            </div>

            <p className={autoSendAction.enabled ? "settings-status" : "settings-status settings-status--warn"}>
              自动发送状态：{autoSendAction.reason}
            </p>

            {safetySummary && (
              <div className={`greeting-preflight greeting-preflight--${isAutoSendReady ? safetySummary.status : "error"}`}>
                <strong>自动发送安全阈值：{isAutoSendReady ? "正常" : "不可发送"}</strong>
                <span className="tag tag--muted">今日 {safetySummary.summary.sentToday}/{safetySummary.summary.dailyLimit}</span>
                <span className={safetySummary.summary.failedStreak >= 3 ? "tag tag--red" : "tag tag--green"}>连续失败 {safetySummary.summary.failedStreak}</span>
                {!bossLogin?.logged_in && <span className="tag tag--red">BOSS 登录未验证</span>}
                {safetySummary.summary.grayMode && (
                  <span className={safetySummary.summary.grayMode.batchAllowed ? "tag tag--green" : "tag tag--muted"}>
                    {safetySummary.summary.grayMode.batchAllowed ? "灰度已通过" : safetySummary.summary.grayMode.message}
                  </span>
                )}
                {safetySummary.checks.map(check => (
                  <span key={check.key} className={`tag ${check.status === "error" ? "tag--red" : check.status === "ok" ? "tag--green" : "tag--muted"}`}>
                    {formatSafetyCheckMessage(check)}
                  </span>
                ))}
              </div>
            )}

            {finalConfirmation && (
              <div className={`greeting-preflight greeting-preflight--${finalConfirmation.status === "ok" ? "ok" : "error"}`}>
                <strong>最终确认摘要：{finalConfirmation.summary.jobCount} 个岗位 · 剩余额度 {finalConfirmation.summary.remaining}</strong>
                <span className="tag tag--muted">有效话术 {finalConfirmation.summary.validMessages}</span>
                <span className="tag tag--muted">链接 {finalConfirmation.links.length}</span>
                {finalConfirmation.riskItems.map(item => <span key={item} className="tag tag--red">{item}</span>)}
              </div>
            )}

            {preflightResult && (
              <div className={`greeting-preflight greeting-preflight--${preflightResult.status}`}>
                <strong>发送前预检：{preflightResult.status === "ok" ? "通过" : "需处理"}</strong>
                {preflightResult.checks.map(check => (
                  <span key={check.key} className={`tag ${check.status === "ok" ? "tag--green" : "tag--red"}`}>
                    {check.message}
                  </span>
                ))}
              </div>
            )}

            {selectorHealth && (
              <div className={`greeting-preflight greeting-preflight--${selectorHealth.status}`}>
                <strong>页面可用性：{selectorHealth.company}</strong>
                {selectorHealth.checks.map(check => (
                  <span key={check.key} className={`tag ${check.status === "ok" ? "tag--green" : check.status === "warn" ? "tag--muted" : "tag--red"}`}>
                    {check.message}
                  </span>
                ))}
              </div>
            )}

            {acceptancePlan && (
              <div className="greeting-acceptance-plan">
                <strong>人工验收模式 · {acceptancePlan.company}</strong>
                {acceptancePlan.steps.map((step, index) => (
                  <div key={step.key} className="greeting-acceptance-step">
                    <span>{index + 1}</span>
                    <div>
                      <b>{step.label}</b>
                      <p>{step.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="greeting-workbench__grid">
              <div className="greeting-metric">
                <span>本次已选</span>
                <strong>{greetingTargetIds.length}</strong>
              </div>
              <div className="greeting-metric">
                <span>{currentFilterLabel}</span>
                <strong>{filteredGreetingJobs.length}</strong>
              </div>
              <div className="greeting-metric">
                <span>可生成</span>
                <strong>{candidateResult?.summary.candidateCount ?? "-"}</strong>
              </div>
              <div className="greeting-metric">
                <span>已跳过</span>
                <strong>{candidateResult?.summary.skippedCount ?? "-"}</strong>
              </div>
              <div className="greeting-metric">
                <span>确认已发</span>
                <strong>{sendResult?.summary.sent ?? 0}</strong>
              </div>
              <div className="greeting-metric">
                <span>累计发送</span>
                <strong>{greetingStats?.summary.sent ?? "-"}</strong>
              </div>
              <div className="greeting-metric">
                <span>累计失败</span>
                <strong>{greetingStats?.summary.failed ?? "-"}</strong>
              </div>
              <div className="greeting-metric">
                <span>待跟进</span>
                <strong>{followups?.summary.pendingFollowups ?? "-"}</strong>
              </div>
              <div className="greeting-metric">
                <span>已回复</span>
                <strong>{greetingStats?.summary.replies ?? replyRecords.length}</strong>
              </div>
            </div>

            {followups?.items.length ? (
              <div className="greeting-followup-list">
                <strong>待跟进提醒</strong>
                {followups.items.slice(0, 5).map(item => (
                  <span key={item.jobId} className="tag tag--muted">
                    {item.company} · {item.windowHours}h
                  </span>
                ))}
              </div>
            ) : null}

            {sendResult && (
              <div className="greeting-send-summary">
                <strong>发送确认结果</strong>
                <span>已确认 {sendResult.summary.sent} 条</span>
                <span>跳过 {sendResult.summary.skipped} 条</span>
                <span>失败 {sendResult.summary.failed} 条</span>
                <span>今日上限 {sendResult.summary.dailyLimit} 条</span>
              </div>
            )}

            {(candidateResult?.skipped.length) ? (
              <div className="greeting-skip-list">
                <strong>跳过原因</strong>
                <button
                  type="button"
                  className="button-quiet button-quiet--sm"
                  onClick={() => setCandidateResult(previous => previous ? {
                    ...previous,
                    skipped: [],
                    summary: { ...previous.summary, skippedCount: 0 },
                  } : previous)}
                >
                  清空跳过原因
                </button>
                {(candidateResult?.skipped || []).slice(0, 6).map(item => (
                  <span key={`${item.jobId}-${item.reason}`} className="tag tag--muted">
                    {item.company} · {item.reason}
                  </span>
                ))}
              </div>
            ) : null}

          </div>
        </div>
      )}

      {jobs.length > 0 && filteredGreetingJobs.length === 0 && (
        <div className="panel panel-strong">
          <div className="panel-inner">
            <EmptyState icon="🔎" title="当前范围暂无岗位" desc="切换本次批量范围，或回到岗位模块补齐 JD、话术和筛选条件。" />
          </div>
        </div>
      )}

      {filteredGreetingJobs.length > 0 && (
        <div className="greeting-list-toolbar">
          <div className="greeting-list-toolbar__meta">
            <strong>{currentFilterLabel}</strong>
            <span>显示 {filteredGreetingJobs.length} 个岗位，本次已选 {greetingTargetIds.length} 个</span>
          </div>
          <div className="greeting-list-toolbar__actions">
            <button type="button" className="button-secondary" onClick={selectVisibleGreetingJobs}>全选当前</button>
            <button type="button" className="button-secondary" onClick={unselectVisibleGreetingJobs}>取消当前</button>
            <button type="button" className="button-secondary" onClick={invertVisibleGreetingJobs}>反选当前</button>
            <button type="button" className="button-quiet" onClick={() => setGreetingSelectedIds([])}>清空全部</button>
          </div>
        </div>
      )}

      {filteredGreetingJobs.map(job => {
	        const opt = optimizations[job.id];
	        const greeting = greetingTexts[job.id];
          const isGreetingRevealed = revealedGreetingIds.includes(job.id);
          const jobAcceptance = acceptanceRecords.find(record => record.jobId === job.id);
          const jobReply = replyRecords.find(record => record.jobId === job.id);
          const isBatchSelected = greetingTargetSet.has(job.id);
	        const readyItems = [
	          { label: "话术", ok: !!greeting },
	          { label: "简历", ok: !!opt },
	          { label: "PDF", ok: !!opt },
	          { label: "招呼", ok: !!greetedStatus[job.id] },
	        ];
	        return (
	          <div key={job.id} className={`panel panel-strong greeting-job-card${isBatchSelected ? " greeting-job-card--selected" : ""}`}>
	            <div className="panel-inner">
              {/* 岗位信息头 */}
              <div className="page-section__top">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="greeting-job-heading">
                    <label className="greeting-job-select">
                      <input
                        type="checkbox"
                        checked={isBatchSelected}
                        onChange={event => toggleGreetingJob(job.id, event.target.checked)}
                      />
                      <span>加入本次批量</span>
                    </label>
                    <strong style={{ fontSize: 15 }}>{job.title}</strong>
                  </div>
                  <p className="text-muted" style={{ fontSize: 13, marginTop: 2 }}>{job.company} · {job.city} · {job.salary}</p>
                </div>
	                <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                  <a href={bossUrl(job)} target="_blank" rel="noopener noreferrer" className="button-quiet" style={{ textDecoration: "none" }}>
                    🔗 BOSS详情
                  </a>
                  <button type="button" className={greetedStatus[job.id] ? "tag tag--green" : "tag tag--muted"}
                    onClick={() => markGreeted(job.id)} style={{ cursor: "pointer", border: "none" }}>
                    {greetedStatus[job.id] ? "✓ 已招呼" : "标记已招呼"}
                  </button>
                  <button type="button" className="button-quiet" onClick={() => recordAcceptance(job)} style={{ fontSize: 12 }}>
                    记录验收
                  </button>
                  <button type="button" className="button-quiet" onClick={() => recordReply(job)} style={{ fontSize: 12 }}>
                    记录回复
                  </button>
                  {(customTags[job.id] || []).map((tag, index) => <span key={`${job.id}-${tag}-${index}`} className="tag">{tag}</span>)}
	                  <input className="form-input form-input--inline" style={{ width: 80, fontSize: 11, padding: "3px 8px" }}
	                    placeholder="添加标签" value={tagInputs[job.id] || ""}
	                    onChange={e => setTagInputs(prev => ({ ...prev, [job.id]: e.target.value }))}
	                    onKeyDown={e => { if (e.key === "Enter") addCustomTag(job.id, tagInputs[job.id] || ""); }} />
	                </div>
	              </div>
	              <div className="job-tags" style={{ marginTop: 12 }}>
	                {readyItems.map(item => (
	                  <span key={item.label} className={`tag ${item.ok ? "tag--green" : "tag--muted"}`}>
	                    {item.ok ? "已准备" : "待处理"} · {item.label}
	                  </span>
	                ))}
                  {jobAcceptance && <span className="tag tag--green">验收: {jobAcceptance.result === "passed" ? "通过" : "需复核"}</span>}
                  {jobReply && <span className="tag tag--active">回复: {jobReply.replyType === "positive" ? "积极" : "已记录"}</span>}
	              </div>
                {(jobAcceptance || jobReply) && (
                  <div className="greeting-record-strip">
                    {jobAcceptance && <span>最近验收：{jobAcceptance.note || jobAcceptance.result}</span>}
                    {jobReply && <span>最近回复：{jobReply.content} · {jobReply.nextAction}</span>}
                  </div>
                )}

              {/* 打招呼语 */}
              <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
                <div className="toolbar-row" style={{ marginBottom: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>💬 打招呼语</span>
                  <button type="button" className="button-secondary"
                    disabled={!!loading[job.id + "-greet"]}
                    onClick={() => onGenerateGreeting(job)} style={{ fontSize: 12 }}>
                    {greeting ? "重新生成" : loading[job.id + "-greet"] || "AI 生成"}
                  </button>
                  {greeting && (
                    <button type="button" className="button-quiet" onClick={() => copyGreeting(greeting, job.id)} style={{ fontSize: 12 }}>
                      {copiedId === job.id ? "✓ 已复制" : "📋 复制"}
                    </button>
                  )}
                  {greeting && (
                    <button type="button" className="button-quiet" onClick={() => setRevealedGreetingIds(previous => previous.includes(job.id) ? previous.filter(id => id !== job.id) : [...previous, job.id])} style={{ fontSize: 12 }}>
                      {isGreetingRevealed ? "显示已脱敏内容" : "编辑完整话术"}
                    </button>
                  )}
                </div>
                {greeting ? (
                  <>
	              <textarea className="form-input" value={isGreetingRevealed ? greeting : maskGreetingSensitiveText(greeting)} readOnly={!isGreetingRevealed}
	                    onChange={e => {
	                      if (!isGreetingRevealed) return;
	                      const next = { ...greetingTexts, [job.id]: e.target.value };
	                      dispatch(actions.setGreetingTexts(next));
	                      saveGreetingDrafts(next).catch((err) => {
	                        setError(err instanceof Error ? err.message : "话术保存失败");
	                      });
	                    }}
                    rows={3} style={{ width: "100%", fontSize: 13 }} />
                    {validationResults[job.id] && (
                      <p className={validationResults[job.id].ok ? "text-success" : "text-danger"} style={{ fontSize: 12, marginTop: 6 }}>
                        {validationResults[job.id].ok ? "校验通过，可以进入人工确认。" : `校验未通过：${validationResults[job.id].reasons.join("、")}`}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-muted" style={{ fontSize: 13 }}>点击生成定制打招呼语</p>
                )}
              </div>

              {/* AI 简历优化 */}
              <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
                <div className="toolbar-row" style={{ marginBottom: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>🔧 AI 简历优化</span>
                  <button type="button" className="button-secondary"
                    disabled={!!loading[job.id + "-opt"]}
                    onClick={() => onOptimize(job)} style={{ fontSize: 12 }}>
                    {opt ? "重新优化" : loading[job.id + "-opt"] || "AI 优化简历"}
                  </button>
                  {opt && (
                    <>
                    <select
                      className="form-input form-input--inline"
                      value={pdfTemplate}
                      onChange={e => setPdfTemplate(e.target.value as "modern" | "classic" | "ats")}
                      style={{ fontSize: 12, minWidth: 120 }}
                      title="PDF 模板"
                    >
                      <option value="modern">续页单栏</option>
                      <option value="classic">经典双栏</option>
                      <option value="ats">紧凑 ATS</option>
                    </select>
                    <button type="button" className="button-quiet" onClick={() => onRecommendTemplate(job)} style={{ fontSize: 12 }}>
                      推荐模板
                    </button>
                    <button type="button" className="button-secondary"
                      disabled={!!loading[job.id + "-preview"]}
                      onClick={() => onPreviewPdf(job)} style={{ fontSize: 12 }}>
                      {loading[job.id + "-preview"] || "预览PDF"}
                    </button>
                    <button type="button" className="button-secondary"
                      disabled={!!loading[job.id + "-pdf"]}
                      onClick={() => onExportPdf(job)} style={{ fontSize: 12 }}>
                      {loading[job.id + "-pdf"] || "📄 下载PDF"}
                    </button>
                    </>
                  )}
                </div>
                {pdfTemplateReason && <p className="text-muted" style={{ fontSize: 12, marginTop: -4 }}>{pdfTemplateReason}</p>}
                {opt && (
                  <div className="panel panel-muted" style={{ marginBottom: 12 }}>
                    <div className="panel-inner" style={{ padding: "14px 18px" }}>
                      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>📋 优化结果</div>
                      {opt.tailored_summary && <p style={{ fontSize: 12, marginBottom: 8, lineHeight: 1.5 }}>{opt.tailored_summary}</p>}
                      {opt.optimized_bullets?.length > 0 && (
                        <ul style={{ margin: "4px 0", paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                          {opt.optimized_bullets.slice(0, 10).map((b, i) => <li key={i}>{b}</li>)}
                        </ul>
                      )}
                      <div className="job-tags" style={{ marginTop: 8 }}>
                        {opt.matched_skills?.map(s => <span key={s} className="tag tag--green">{s} ✓</span>)}
                        {opt.missing_skills?.map(s => <span key={s} className="tag tag--red">{s} ✗</span>)}
                      </div>
                    </div>
                  </div>
                )}
                {opt && (
                  <ChatPanel chatKey={`greet-opt-${job.id}`} step="optimize" context={{ job_title: job.title, company: job.company, optimization: opt }}
                    profileName={resumeProfile?.name} title="与 AI 讨论修订" placeholder="与 AI 讨论如何进一步优化…"
                    onApply={async (messages) => {
                      if (!resumeProfile) { setError("请先上传简历"); return; }
                      try {
                        const jdA = await ensureJDAnalysis(job);
                        const data = await aiOptimizeResume(resumeProfile, { id: job.id, title: job.title, company: job.company, jd_text: job.jd_text }, null, jdA || undefined, messages);
                        dispatch(actions.setOptimizations({ ...optimizations, [job.id]: data }));
                        dispatch(actions.mergeChatMessage(job.id, messages));
                      } catch { setError("应用优化失败"); }
                    }} />
                )}
              </div>
            </div>
          </div>
        );
      })}
    </section>
  );
}
