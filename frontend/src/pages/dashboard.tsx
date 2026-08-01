import { useEffect, useRef, useState } from "react";
import { clearAssistantPromptVersions, compareAssistantPromptVersions, deleteAssistantPromptVersion, editAssistantDeepReport, exportAssistantDeepReportUrl, getApplicationBoard, getApplicationFunnel, getApplicationStrategy, getApplicationTimeline, getAssistantDeepReport, getAssistantPromptVersions, getDashboardSummary, getDashboardTrends, getDataQualityCenter, getDiligenceReports, getFollowups, getGreetingTemplateEffectiveness, getInterviewPrep, getJdQuality, getJobPoolQuality, getOnboardingGuide, getRankingResults, getReviewCenter, getResumeRewriteAdvice, getRiskExplanation, getWeeklyReport, getWorkflowCenter, listJobPool, moveApplicationBoardJob, repairDataQuality } from "../lib/api";
import { useWorkflowState } from "../lib/store";
import { ensureDashboardPanelVisible } from "../lib/dashboardPanels";
import { resolveDashboardQualityFilter, setDashboardNavigation, type JobQualityFilter } from "../lib/dashboardNavigation";
import { buildJobNavigation, dashboardScopeLabel, type DashboardScope } from "../lib/dashboardScope";
import type { ApplicationBoard, ApplicationFunnel, ApplicationStrategy, ApplicationTimeline, AssistantPromptVersionCompare, AssistantPromptVersions, DashboardSummary, DashboardTrendReport, DataQualityCenter, DeepReportSections, FollowupReminder, GreetingTemplateEffectiveness, InterviewPrep, JdQualityInsight, JobApplicationStatus, JobPoolQuality, JobPosting, OnboardingGuide, ReviewCenter, ResumeRewriteAdvice, RiskExplanation, WeeklyReport, WorkflowCenter } from "../lib/types";
import { ErrorBanner, Spinner } from "../components/SharedUI";
import AiFeedbackButtons from "../components/AiFeedbackButtons";

type DashboardPanelKey =
  | "readiness" | "metrics" | "trends" | "onboarding" | "quality"
  | "actions" | "funnel" | "templateEffectiveness" | "board" | "weekly"
  | "workflow" | "timeline" | "assistant" | "followups" | "promptVersions"
  | "review";

const DASHBOARD_PANEL_LABELS: Record<DashboardPanelKey, string> = {
  readiness: "流程引导",
  metrics: "指标概览",
  trends: "30天趋势",
  onboarding: "新手引导",
  quality: "数据质量",
  actions: "下一步建议",
  funnel: "转化复盘",
  templateEffectiveness: "招呼语效果",
  board: "CRM 看板",
  weekly: "求职周报",
  workflow: "任务中心",
  timeline: "投递时间线",
  assistant: "智能助理",
  followups: "跟进提醒",
  promptVersions: "AI 版本记录",
  review: "复盘中心",
};

const DEFAULT_PANEL_ORDER: DashboardPanelKey[] = [
  "readiness", "metrics", "trends", "onboarding", "quality",
  "actions", "funnel", "templateEffectiveness", "board", "weekly",
  "workflow", "timeline", "assistant", "followups", "promptVersions",
  "review",
];

const PANEL_STORAGE_KEY = "boss-dashboard-panel-config";

function loadDashboardPanelConfig(): { order: DashboardPanelKey[]; hidden: DashboardPanelKey[] } {
  try {
    const raw = localStorage.getItem(PANEL_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      const order = (parsed.order || DEFAULT_PANEL_ORDER).filter((k: string) => k in DASHBOARD_PANEL_LABELS);
      const hidden = (parsed.hidden || []).filter((k: string) => k in DASHBOARD_PANEL_LABELS);
      for (const key of DEFAULT_PANEL_ORDER) { if (!order.includes(key)) order.push(key); }
      return { order, hidden };
    }
  } catch {}
  return { order: [...DEFAULT_PANEL_ORDER], hidden: [] };
}


const statusOptions: Array<{ key: JobApplicationStatus; label: string }> = [
  { key: "pending", label: "待处理" },
  { key: "greeted", label: "已沟通" },
  { key: "applied", label: "已投递" },
  { key: "interviewing", label: "面试中" },
  { key: "rejected", label: "已拒绝" },
  { key: "abandoned", label: "已放弃" },
];


export default function DashboardPage({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const workflow = useWorkflowState();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [funnel, setFunnel] = useState<ApplicationFunnel | null>(null);
  const [timeline, setTimeline] = useState<ApplicationTimeline | null>(null);
  const [applicationBoard, setApplicationBoard] = useState<ApplicationBoard | null>(null);
  const [workflowCenter, setWorkflowCenter] = useState<WorkflowCenter | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingGuide | null>(null);
  const [reviewCenter, setReviewCenter] = useState<ReviewCenter | null>(null);
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReport | null>(null);
  const [trendReport, setTrendReport] = useState<DashboardTrendReport | null>(null);
  const [dataQuality, setDataQuality] = useState<DataQualityCenter | null>(null);
  const [promptVersions, setPromptVersions] = useState<AssistantPromptVersions | null>(null);
  const [promptCompare, setPromptCompare] = useState<AssistantPromptVersionCompare | null>(null);
  const [jobQuality, setJobQuality] = useState<JobPoolQuality | null>(null);
  const [templateEffectiveness, setTemplateEffectiveness] = useState<GreetingTemplateEffectiveness | null>(null);
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [followups, setFollowups] = useState<FollowupReminder[]>([]);
  const [assistant, setAssistant] = useState<{
    strategy?: ApplicationStrategy;
    jdQuality?: JdQualityInsight;
    rewrite?: ResumeRewriteAdvice;
    interview?: InterviewPrep;
    risk?: RiskExplanation;
  }>({});
  const [loading, setLoading] = useState(true);
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [deepReport, setDeepReport] = useState<Record<string, any> | null>(null);
  const [reportSummary, setReportSummary] = useState("");
  const [reportSections, setReportSections] = useState<DeepReportSections>({});
  const [reportStatus, setReportStatus] = useState("");
  const [qualityRepairStatus, setQualityRepairStatus] = useState("");
  const [error, setError] = useState("");
  const [panelConfig, setPanelConfig] = useState(loadDashboardPanelConfig);
  const [showPanelCustomizer, setShowPanelCustomizer] = useState(false);
  const [promptVersionsCollapsed, setPromptVersionsCollapsed] = useState(true);
  const [promptVersionsRefreshing, setPromptVersionsRefreshing] = useState(false);
  const [collapsedBoardColumns, setCollapsedBoardColumns] = useState<Set<string>>(() => new Set());
  const reviewPanelRef = useRef<HTMLDivElement | null>(null);

  async function loadSummary() {
    setLoading(true);
    setError("");
    try {
      const [nextSummary, pool, reminders, nextFunnel, nextTimeline, nextBoard, nextWorkflowCenter, nextOnboarding, nextReview, nextWeeklyReport, nextTrendReport, nextDataQuality, nextPromptVersions, nextJobQuality, nextTemplateEffectiveness] = await Promise.all([
        getDashboardSummary(workflow.selectedJobIds),
        listJobPool(),
        getFollowups(),
        getApplicationFunnel(),
        getApplicationTimeline(),
        getApplicationBoard(workflow.selectedJobIds),
        getWorkflowCenter(),
        getOnboardingGuide(workflow.selectedJobIds),
        getReviewCenter(),
        getWeeklyReport(),
        getDashboardTrends(30),
        getDataQualityCenter(workflow.selectedJobIds),
        getAssistantPromptVersions(),
        getJobPoolQuality(),
        getGreetingTemplateEffectiveness(),
      ]);
      setSummary(nextSummary);
      setJobs(pool.jobs || []);
      setFollowups(reminders.reminders || []);
      setFunnel(nextFunnel);
      setTimeline(nextTimeline);
      setApplicationBoard(nextBoard);
      setWorkflowCenter(nextWorkflowCenter);
      setOnboarding(nextOnboarding);
      setReviewCenter(nextReview);
      setWeeklyReport(nextWeeklyReport);
      setTrendReport(nextTrendReport);
      setDataQuality(nextDataQuality);
      setPromptVersions(nextPromptVersions);
      setJobQuality(nextJobQuality);
      setTemplateEffectiveness(nextTemplateEffectiveness);
    } catch (err) {
      setError(err instanceof Error ? err.message : "仪表盘加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSummary();
  }, []);

  async function refreshLiveDashboard() {
    try {
      const [nextSummary, pool, reminders, nextFunnel, nextTimeline, nextBoard, nextWorkflowCenter, nextDataQuality, nextOnboarding, nextReview, nextWeeklyReport, nextTrendReport, nextPromptVersions, nextJobQuality, nextTemplateEffectiveness] = await Promise.all([
        getDashboardSummary(workflow.selectedJobIds),
        listJobPool(),
        getFollowups(),
        getApplicationFunnel(),
        getApplicationTimeline(),
        getApplicationBoard(workflow.selectedJobIds),
        getWorkflowCenter(),
        getDataQualityCenter(workflow.selectedJobIds),
        getOnboardingGuide(workflow.selectedJobIds),
        getReviewCenter(),
        getWeeklyReport(),
        getDashboardTrends(30),
        getAssistantPromptVersions(),
        getJobPoolQuality(),
        getGreetingTemplateEffectiveness(),
      ]);
      setSummary(nextSummary);
      setJobs(pool.jobs || []);
      setFollowups(reminders.reminders || []);
      setFunnel(nextFunnel);
      setTimeline(nextTimeline);
      setApplicationBoard(nextBoard);
      setWorkflowCenter(nextWorkflowCenter);
      setDataQuality(nextDataQuality);
      setOnboarding(nextOnboarding);
      setReviewCenter(nextReview);
      setWeeklyReport(nextWeeklyReport);
      setTrendReport(nextTrendReport);
      setPromptVersions(nextPromptVersions);
      setJobQuality(nextJobQuality);
      setTemplateEffectiveness(nextTemplateEffectiveness);
    } catch {
      // 静默轮询失败不覆盖用户当前看到的数据，手动刷新仍会显示具体错误。
    }
  }

  useEffect(() => {
    void refreshLiveDashboard();
    const timer = window.setInterval(refreshLiveDashboard, 10000);
    const onFocus = () => { void refreshLiveDashboard(); };
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [workflow.selectedJobIds]);

  async function refreshPromptVersions(silent = false) {
    if (!silent) setPromptVersionsRefreshing(true);
    try {
      setPromptVersions(await getAssistantPromptVersions());
    } catch (err) {
      if (!silent) setError(err instanceof Error ? err.message : "AI 版本记录刷新失败");
    } finally {
      if (!silent) setPromptVersionsRefreshing(false);
    }
  }

  useEffect(() => {
    const timer = window.setInterval(() => {
      refreshPromptVersions(true);
    }, 15000);
    return () => window.clearInterval(timer);
  }, []);


  function togglePanelHidden(key: DashboardPanelKey) {
    setPanelConfig(prev => {
      const hidden = prev.hidden.includes(key) ? prev.hidden.filter(k => k !== key) : [...prev.hidden, key];
      const next = { ...prev, hidden };
      localStorage.setItem(PANEL_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }

  function goToJobs(qualityFilter: JobQualityFilter = "", applicationStatus = "", decisionStatus = "", scope: DashboardScope = "selected") {
    setDashboardNavigation(buildJobNavigation({ qualityFilter, applicationStatus, decisionStatus, scope, selectedCount: summary?.jobs.total || 0 }));
    onNavigate?.("jobs");
  }

  function navigateQualityCheck(key: string, page: string) {
    const qualityFilter = resolveDashboardQualityFilter(key);
    if (qualityFilter) return goToJobs(qualityFilter);
    onNavigate?.(page);
  }

  function movePanel(key: DashboardPanelKey, direction: number) {
    setPanelConfig(prev => {
      const order = [...prev.order];
      const idx = order.indexOf(key);
      const newIdx = idx + direction;
      if (newIdx < 0 || newIdx >= order.length) return prev;
      [order[idx], order[newIdx]] = [order[newIdx], order[idx]];
      const next = { ...prev, order };
      localStorage.setItem(PANEL_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }

  function panelVisible(key: DashboardPanelKey): boolean {
    return !panelConfig.hidden.includes(key);
  }

  function panelOrder(key: DashboardPanelKey): number {
    return panelConfig.order.indexOf(key);
  }

  function showReviewPanel() {
    setPanelConfig(prev => {
      const next = ensureDashboardPanelVisible(prev, "review");
      localStorage.setItem(PANEL_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
    window.setTimeout(() => {
      reviewPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  }

  function toggleBoardColumn(columnKey: string) {
    setCollapsedBoardColumns(previous => {
      const next = new Set(previous);
      if (next.has(columnKey)) next.delete(columnKey);
      else next.add(columnKey);
      return next;
    });
  }

  const focusJob = jobs.find(job => workflow.selectedJobIds.includes(job.id)) || jobs[0] || null;

  async function moveBoardJob(jobId: string, status: JobApplicationStatus) {
    try {
      const result = await moveApplicationBoardJob(jobId, status, "CRM 看板更新");
      const [nextTimeline, nextFunnel, nextSummary] = await Promise.all([
        getApplicationTimeline(),
        getApplicationFunnel(),
        getDashboardSummary(workflow.selectedJobIds),
      ]);
      setApplicationBoard(result.board);
      setTimeline(nextTimeline);
      setFunnel(nextFunnel);
      setSummary(nextSummary);
      setJobs(prev => prev.map(job => job.id === jobId ? { ...job, application_status: result.application_status, application_note: result.application_note, application_updated_at: result.application_updated_at, greeted: result.greeted } : job));
    } catch (err) {
      setError(err instanceof Error ? err.message : "状态更新失败");
    }
  }

  async function runAssistant() {
    if (!focusJob) return;
    setAssistantLoading(true);
    setError("");
    try {
      const [diligence, rankings] = await Promise.all([getDiligenceReports(), getRankingResults()]);
      const diligenceReport = diligence.reports[focusJob.company] || Object.values(diligence.reports).find(report =>
        report.companyName === focusJob.company || report.sourceCompanyName === focusJob.company || report.companyKey === focusJob.company_key
      );
      const ranking = rankings.rankings.find(item => item.jobId === focusJob.id);
      const base = { job: focusJob, resume: workflow.resumeProfile || {}, diligence: diligenceReport || {}, ranking: ranking || {} };
      const [strategy, jdQuality, rewrite, interview, risk] = await Promise.all([
        getApplicationStrategy({ ...base, job_id: focusJob.id }),
        getJdQuality({ job: focusJob }),
        getResumeRewriteAdvice(base),
        getInterviewPrep(base),
        getRiskExplanation({ diligence: diligenceReport || {} }),
      ]);
      const report = await getAssistantDeepReport(base) as Record<string, any>;
      setDeepReport(report);
      setReportSummary(String(report?.manualReport?.summary || report?.aiReport?.summary || ""));
      setReportSections({
        summary: String(report?.manualReport?.sections?.summary || ""),
        strategy: String(report?.manualReport?.sections?.strategy || ""),
        match: String(report?.manualReport?.sections?.match || ""),
        risk: String(report?.manualReport?.sections?.risk || ""),
        interview: String(report?.manualReport?.sections?.interview || ""),
        actions: String(report?.manualReport?.sections?.actions || ""),
      });
      setAssistant({ strategy, jdQuality, rewrite, interview, risk });
    } catch (err) {
      setError(err instanceof Error ? err.message : "智能助理生成失败");
    } finally {
      setAssistantLoading(false);
    }
  }

  async function saveReportEdit() {
    if (!focusJob || !reportSummary.trim()) return;
    try {
      await editAssistantDeepReport({ job_id: focusJob.id, summary: reportSummary.trim(), sections: reportSections });
      setReportStatus("人工复核已保存");
    } catch (err) {
      setReportStatus(err instanceof Error ? err.message : "保存失败");
    }
  }

  async function runQualityRepair() {
    setQualityRepairStatus("修复中...");
    try {
      const result = await repairDataQuality(["tag_missing_jd", "tag_low_quality_jd", "tag_suspected_expired"]);
      setDataQuality(result.quality);
      setQualityRepairStatus(`已更新 ${result.updated} 个岗位`);
      const pool = await listJobPool();
      setJobs(pool.jobs || []);
    } catch (err) {
      setQualityRepairStatus(err instanceof Error ? err.message : "修复失败");
    }
  }

  async function loadPromptCompare(jobId: string) {
    try {
      setPromptCompare(await compareAssistantPromptVersions(jobId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "版本对比失败");
    }
  }

  async function onDeletePromptVersion(recordId: string) {
    try {
      await deleteAssistantPromptVersion(recordId);
      if (promptCompare?.versions.some(item => item.id === recordId)) setPromptCompare(null);
      await refreshPromptVersions(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除版本记录失败");
    }
  }

  async function onClearPromptVersions() {
    if (!confirm("确定清空 AI 版本记录？此操作只清理记录列表，不影响已生成的报告。")) return;
    try {
      await clearAssistantPromptVersions();
      setPromptCompare(null);
      await refreshPromptVersions(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "清空版本记录失败");
    }
  }

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">总览</p>
          <h2 className="page-title">求职流程仪表盘</h2>
          <p className="page-copy">集中查看岗位池、JD、尽调、排序和决策标签，优先处理最影响推进的事项。</p>
        </div>
        <button type="button" className="button-secondary" onClick={loadSummary}>刷新</button>
      </div>


      <div className="toolbar-row" style={{ marginBottom: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="button-quiet" onClick={() => setShowPanelCustomizer(v => !v)} style={{ fontSize: 12 }}>
          {showPanelCustomizer ? "完成自定义" : "⚙ 自定义面板"}
        </button>
      </div>
      {showPanelCustomizer && (
        <div className="panel panel-strong" style={{ marginBottom: 12 }}>
          <div className="panel-inner" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <span className="page-kicker" style={{ marginRight: 4 }}>面板管理</span>
            {panelConfig.order.map((key, index) => {
              const hidden = panelConfig.hidden.includes(key);
              return (
                <span key={key} className="tag" style={{ opacity: hidden ? 0.4 : 1, display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 6px" }}>
                  <input type="checkbox" checked={!hidden} onChange={() => togglePanelHidden(key)} style={{ margin: 0, cursor: "pointer" }} title={hidden ? "显示" : "隐藏"} />
                  <span style={{ fontSize: 12 }}>{DASHBOARD_PANEL_LABELS[key]}</span>
                  <button type="button" className="button-quiet" disabled={index === 0} onClick={() => movePanel(key, -1)} style={{ padding: "0 2px", fontSize: 10, lineHeight: 1, cursor: index === 0 ? "default" : "pointer" }}>↑</button>
                  <button type="button" className="button-quiet" disabled={index === panelConfig.order.length - 1} onClick={() => movePanel(key, 1)} style={{ padding: "0 2px", fontSize: 10, lineHeight: 1, cursor: index === panelConfig.order.length - 1 ? "default" : "pointer" }}>↓</button>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}
      {loading && <div className="panel panel-strong"><div className="panel-inner"><Spinner text="正在加载仪表盘..." /></div></div>}

      {summary && (
        <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          {panelVisible("readiness") && (
          <div className="readiness-panel" style={{ order: panelOrder("readiness") }}>
            <div className="readiness-panel__main">
              <span className="page-kicker">上线级流程引导 · {dashboardScopeLabel("selected", summary.jobs.total)}</span>
              <h3>{stageLabel(summary.readiness.stage)}</h3>
              <p>{summary.readiness.nextAction.reason}</p>
              <button type="button" className="button-primary" onClick={() => onNavigate?.(summary.readiness.nextAction.page)}>
                {summary.readiness.nextAction.label}
              </button>
            </div>
            <div className="readiness-score" aria-label="流程质量分">
              <span>流程质量</span>
              <div className="readiness-score__value">
                <strong>{summary.readiness.qualityScore}</strong>
                <em>/100</em>
              </div>
              <small>流程完成度，不等同于数据质量</small>
            </div>
            <div className="readiness-blockers">
              <button type="button" className="readiness-blocker readiness-blocker--selected" onClick={() => goToJobs()}>
                <span>已选岗位</span>
                <strong>{summary.jobs.total}</strong>
              </button>
              {summary.readiness.blockers.length > 0 ? (
                summary.readiness.blockers.slice(0, 4).map(item => (
                  <button
                    type="button"
                    key={item.key}
                    className={`readiness-blocker readiness-blocker--${item.severity}`}
                    onClick={() => blockerPage(item.key) === "jobs" ? goToJobs() : onNavigate?.(blockerPage(item.key))}
                  >
                    <span>{item.label}</span>
                    <strong>{item.count}</strong>
                  </button>
                ))
              ) : (
                <div className="readiness-blocker readiness-blocker--clear">
                  <span>暂无关键阻断</span>
                  <strong>✓</strong>
                </div>
              )}
            </div>
          </div>
          )}

          {panelVisible("metrics") && (
          <div className="dashboard-metric-grid" style={{ order: panelOrder("metrics") }}>
            <MetricCard title="岗位总数" value={summary.jobs.total} action="查看岗位" onClick={() => goToJobs()} />
            <MetricCard title="待补 JD" value={summary.jobs.missingJd} tone={summary.jobs.missingJd > 0 ? "warn" : "ok"} action="补全 JD" onClick={() => goToJobs("missing_jd")} />
            <MetricCard title="待尽调公司" value={summary.diligence.pendingCompanies} tone={summary.diligence.pendingCompanies > 0 ? "warn" : "ok"} action="进入尽调" onClick={() => onNavigate?.("diligence")} />
            <MetricCard title="推荐岗位" value={summary.decisions.recommended || summary.ranking.recommended} tone="ok" action="查看排序" onClick={() => onNavigate?.("ranking")} />
            <MetricCard title="风险岗位" value={summary.decisions.risky + summary.jobs.blacklisted} tone={summary.decisions.risky + summary.jobs.blacklisted > 0 ? "danger" : "ok"} action="复核风险" onClick={() => goToJobs("risk_jobs", "", "risky")} />
            <MetricCard title="疑似过期" value={summary.jobs.suspectedExpired} tone={summary.jobs.suspectedExpired > 0 ? "warn" : "ok"} action="清理维护" onClick={() => goToJobs("suspected_expired")} />
            <MetricCard title="AI 反馈" value={jobQuality?.summary.ai_feedback_needs_revision || 0} tone={(jobQuality?.summary.ai_feedback_needs_revision || 0) > 0 ? "warn" : "neutral"} action={`${jobQuality?.summary.ai_feedback_needs_revision || 0} 条需改`} onClick={() => goToJobs("ai_feedback_needs_revision", "", "", "history")} />
          </div>
          )}

          {panelVisible("trends") && trendReport && (
            <div className="panel panel-strong" style={{ order: panelOrder("trends") }}>
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">30 天趋势 · 全库历史</div>
                    <p className="capture-panel-copy">看扩池、JD、尽调、触达和回复是否连续推进。</p>
                  </div>
                  <span className="tag tag--green">回复率 {trendReport.summary.replyRate}%</span>
                </div>
                <div className="dashboard-trend-metrics">
                  <MetricCard title="新增" value={trendReport.summary.capturedJobs} action={`全库 JD ${trendReport.summary.jdReadyRate}%`} onClick={() => goToJobs("", "", "", "history")} />
                  <MetricCard title="尽调" value={trendReport.summary.diligenceDone} action="证据" onClick={() => onNavigate?.("diligence")} />
                  <MetricCard title="发送" value={trendReport.summary.greetingsSent} tone="ok" action="触达" onClick={() => onNavigate?.("greeting")} />
                  <MetricCard title="回复" value={trendReport.summary.replies} tone="ok" action={`积极 ${trendReport.summary.positiveReplyRate}%`} onClick={() => onNavigate?.("greeting")} />
                  <MetricCard title="面试" value={trendReport.summary.interviewing} tone="ok" action={`${trendReport.summary.interviewRate}%`} onClick={() => goToJobs("", "interviewing", "", "history")} />
                </div>
                <div className="dashboard-trend-chart">
                  {trendReport.series.slice(-14).map(day => {
                    const maxValue = Math.max(1, ...trendReport.series.map(item => Math.max(item.capturedJobs, item.greetingsSent, item.replies, item.interviewing)));
                    return (
                      <div key={day.date} className="dashboard-trend-day" title={day.date}>
                        <span style={{ height: `${Math.max(8, day.capturedJobs / maxValue * 100)}%` }} />
                        <span style={{ height: `${Math.max(8, day.greetingsSent / maxValue * 100)}%` }} />
                        <span style={{ height: `${Math.max(8, day.replies / maxValue * 100)}%` }} />
                        <small>{day.date.slice(5)}</small>
                      </div>
                    );
                  })}
                </div>
                <div className="trend-legend">
                  <span>新增岗位</span>
                  <span>已发送</span>
                  <span>已回复</span>
                </div>
              </div>
            </div>
          )}

          {panelVisible("onboarding") && onboarding && (
            <div className="panel panel-strong" style={{ order: panelOrder("onboarding") }}>
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">新手引导</div>
                    <p className="capture-panel-copy">按顺序完成，统计范围为当前勾选的 {onboarding.scope?.selectedJobs ?? 0} 个岗位。</p>
                  </div>
                  <button type="button" className="button-primary" onClick={() => onNavigate?.(onboarding.nextStep.page)}>
                    {onboarding.nextStep.action || onboarding.nextStep.label}
                  </button>
                </div>
                {onboarding.progress && (
                  <div className="onboarding-progress">
                    <span style={{ width: `${onboarding.progress.percent}%` }} />
                    <strong>{onboarding.progress.done}/{onboarding.progress.total}</strong>
                  </div>
                )}
                <div className="dashboard-onboarding-list">
                  {onboarding.steps.map(step => (
                    <button type="button" key={step.key} className={`dashboard-onboarding-step dashboard-onboarding-step--${step.status}`} onClick={() => onNavigate?.(step.page)}>
                      <span>{step.status === "done" ? "✓" : "○"}</span>
                      <strong>{step.label}</strong>
                      <small>{step.reason}</small>
                      <em>{step.action || "查看"}</em>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {panelVisible("quality") && dataQuality && (
            <div className="panel panel-strong" style={{ order: panelOrder("quality") }}>
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">数据质量体检 · {dashboardScopeLabel("selected", summary.jobs.total)}</div>
                    <p className="capture-panel-copy">集中发现会影响排序、尽调、触达和统计准确性的问题。</p>
                  </div>
                  <span className={dataQuality.summary.errors > 0 ? "tag tag--red" : "tag tag--green"}>质量 {dataQuality.summary.score}</span>
                  <button type="button" className="button-secondary button-secondary--sm" onClick={runQualityRepair}>一键修复标签</button>
                </div>
                <div className="data-quality-grid">
                  {dataQuality.checks.map(check => (
                    <button type="button" key={check.key} className={`data-quality-card data-quality-card--${check.severity}`} onClick={() => navigateQualityCheck(check.key, check.page)}>
                      <span>{check.label}</span>
                      <strong>{check.count}</strong>
                      <small>{check.reason}</small>
                    </button>
                  ))}
                </div>
                {qualityRepairStatus && <p className="settings-status">{qualityRepairStatus}</p>}
              </div>
            </div>
          )}

          {panelVisible("actions") && (
          <div className="panel panel-strong" style={{ order: panelOrder("actions") }}>
            <div className="panel-inner">
              <div className="page-section__top">
                <div>
                  <div className="page-kicker">下一步建议</div>
                  <p className="capture-panel-copy">按影响排序，先处理会阻断后续流程的项目。</p>
                </div>
                <span className="tag tag--muted">更新于 {summary.generatedAt.slice(0, 19).replace("T", " ")}</span>
              </div>
              <div className="dashboard-action-list">
                {summary.jobs.missingJd > 0 && <ActionRow title="补齐 JD 详情" desc={`${summary.jobs.missingJd} 个岗位缺少 JD，尽调和排序会受影响。`} action="去处理" onClick={() => goToJobs("missing_jd")} />}
                {summary.diligence.pendingCompanies > 0 && <ActionRow title="完成公司尽调" desc={`${summary.diligence.pendingCompanies} 家公司还没有尽调报告。`} action="去尽调" onClick={() => onNavigate?.("diligence")} />}
                {summary.ranking.total === 0 && summary.jobs.total > 0 && <ActionRow title="生成综合排序" desc="当前还没有排序结果，无法稳定进入打招呼优先级判断。" action="去排序" onClick={() => onNavigate?.("ranking")} />}
                {summary.jobs.suspectedExpired > 0 && <ActionRow title="清理疑似过期岗位" desc="过期岗位会污染排序结果，建议保留或归档。" action="查看岗位" onClick={() => goToJobs("suspected_expired")} />}
                {summary.jobs.total === 0 && <ActionRow title="先选择候选岗位" desc="岗位池已有数据；请在岗位页勾选感兴趣的岗位后再进入后续流程。" action="去岗位页" onClick={() => goToJobs()} />}
              </div>
            </div>
          </div>
          )}

          {panelVisible("funnel") && funnel && (
            <div className="panel panel-strong" style={{ order: panelOrder("funnel") }}>
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">求职转化复盘 · 全库历史</div>
                    <p className="capture-panel-copy">用真实状态反馈调整关键词、筛选条件和投递策略。</p>
                  </div>
                </div>
                <div className="dashboard-funnel-grid">
                  <MetricCard title="已触达" value={funnel.summary.contacted} tone="neutral" action={`${funnel.summary.contactRate}%`} onClick={() => goToJobs("", "greeted", "", "history")} />
                  <MetricCard title="面试中" value={funnel.summary.interviewing} tone="ok" action={`${funnel.summary.interviewRate}%`} onClick={() => goToJobs("", "interviewing", "", "history")} />
                  <MetricCard title="已拒绝" value={funnel.summary.rejected} tone={funnel.summary.rejected > funnel.summary.interviewing ? "warn" : "neutral"} action={`${funnel.summary.rejectionRate}%`} onClick={() => goToJobs("", "rejected", "", "history")} />
                  <MetricCard title="推荐岗位" value={funnel.summary.recommended} tone="ok" action="复盘来源" onClick={() => onNavigate?.("ranking")} />
                </div>
                <div className="dashboard-action-list">
                  {funnel.recommendations.slice(0, 3).map(item => (
                    <ActionRow key={item} title="复盘建议" desc={item} action="查看岗位" onClick={() => onNavigate?.("jobs")} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {panelVisible("templateEffectiveness") && templateEffectiveness && (
            <div className="panel panel-strong" style={{ order: panelOrder("templateEffectiveness") }}>
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">招呼语效果分析 · 全库历史</div>
                    <p className="capture-panel-copy">按岗位类型复盘发送、回复和积极回复，帮助优化下一批话术。</p>
                  </div>
                  <span className="tag tag--green">回复率 {templateEffectiveness.summary.replyRate}%</span>
                </div>
                <div className="dashboard-funnel-grid">
                  <MetricCard title="已发送" value={templateEffectiveness.summary.sent} tone="neutral" action="话术样本" onClick={() => onNavigate?.("greeting")} />
                  <MetricCard title="已回复" value={templateEffectiveness.summary.replies} tone="ok" action={`${templateEffectiveness.summary.replyRate}%`} onClick={() => onNavigate?.("greeting")} />
                  <MetricCard title="积极回复" value={templateEffectiveness.summary.positiveReplies} tone="ok" action={`${templateEffectiveness.summary.positiveRate}%`} onClick={() => onNavigate?.("greeting")} />
                </div>
                <div className="template-effectiveness-list">
                  {templateEffectiveness.byJobType.slice(0, 4).map(item => (
                    <button type="button" key={item.jobType} className="template-effectiveness-item" onClick={() => onNavigate?.("greeting")}>
                      <strong>{item.jobType}</strong>
                      <span>发送 {item.sent} · 回复 {item.replyRate}% · 积极 {item.positiveRate}%</span>
                      <small>平均 {item.avgLength} 字</small>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {panelVisible("board") && applicationBoard && (
            <div className="panel panel-strong" style={{ order: panelOrder("board") }}>
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">求职 CRM 看板 · {dashboardScopeLabel("selected", applicationBoard.summary.total)}</div>
                    <p className="capture-panel-copy">按求职状态查看岗位推进情况。</p>
                  </div>
                  <span className="tag tag--muted">岗位 {applicationBoard.summary.total}</span>
                </div>
                <div className="application-board-grid">
                  {Object.values(applicationBoard.columns).map(column => (
                    <div
                      key={column.key}
                      className="application-board-column application-board-column--drop"
                      onDragOver={event => event.preventDefault()}
                      onDrop={event => {
                        event.preventDefault();
                        const jobId = event.dataTransfer.getData("text/plain");
                        if (jobId && statusOptions.some(option => option.key === column.key)) {
                          void moveBoardJob(jobId, column.key as JobApplicationStatus);
                        }
                      }}
                    >
                      <div className="application-board-column__top">
                        <div className="application-board-column__label"><strong>{column.label}</strong><span>{column.count}</span></div>
                        <button
                          type="button"
                          className="application-board-column__collapse"
                          aria-label={collapsedBoardColumns.has(column.key) ? "展开看板内容" : "收起看板内容"}
                          aria-expanded={!collapsedBoardColumns.has(column.key)}
                          onClick={() => toggleBoardColumn(column.key)}
                        >
                          {collapsedBoardColumns.has(column.key) ? "展开" : "收起"}
                        </button>
                      </div>
                      {!collapsedBoardColumns.has(column.key) && column.jobs.map(job => (
                        <div
                          key={job.id}
                          className="application-board-card"
                          draggable
                          onDragStart={event => {
                            event.dataTransfer.setData("text/plain", job.id);
                            event.dataTransfer.effectAllowed = "move";
                          }}
                        >
                          <button type="button" className="application-board-card__main" onClick={() => goToJobs("", column.key, "", "selected")}>
                            <strong>{job.company}</strong>
                            <span>{job.title}</span>
                            <small>{job.salary || job.note || "暂无备注"}</small>
                          </button>
                          <select
                            className="application-board-select"
                            value={column.key}
                            aria-label="调整求职状态"
                            onChange={event => void moveBoardJob(job.id, event.target.value as JobApplicationStatus)}
                          >
                            {statusOptions.map(option => <option key={option.key} value={option.key}>{option.label}</option>)}
                          </select>
                        </div>
                      ))}
                      {!collapsedBoardColumns.has(column.key) && column.jobs.length === 0 && <p className="application-board-empty">拖到这里</p>}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {panelVisible("weekly") && weeklyReport && (
            <div className="panel panel-strong" style={{ order: panelOrder("weekly") }}>
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">求职周报</div>
                    <p className="capture-panel-copy">最近 {weeklyReport.windowDays} 天的扩池、触达、推进和失败恢复情况。</p>
                  </div>
                  <span className="tag tag--muted">面试率 {weeklyReport.conversion.interviewRate}%</span>
                </div>
                <div className="dashboard-funnel-grid">
                  <MetricCard title="新增岗位" value={weeklyReport.summary.capturedJobs} tone="neutral" action={`JD ${weeklyReport.conversion.jdReadyRate}%`} onClick={() => onNavigate?.("jobs")} />
                  <MetricCard title="完成尽调" value={weeklyReport.summary.diligenceDone} tone="neutral" action="证据复盘" onClick={() => onNavigate?.("diligence")} />
                  <MetricCard title="已发送" value={weeklyReport.summary.greetingsSent} tone="ok" action="触达记录" onClick={() => onNavigate?.("greeting")} />
                  <MetricCard title="失败任务" value={weeklyReport.summary.failedTasks} tone={weeklyReport.summary.failedTasks > 0 ? "warn" : "ok"} action="恢复中心" onClick={() => onNavigate?.("dashboard")} />
                </div>
                {weeklyReport.failureGroups.length > 0 && (
                  <div className="weekly-failure-strip">
                    {weeklyReport.failureGroups.slice(0, 4).map(group => (
                      <div key={group.category} className="weekly-failure-item">
                        <strong>{group.label}</strong>
                        <span>{group.count} 个 · 可重试 {group.retryable}</span>
                        <p>{group.action}</p>
                      </div>
                    ))}
                  </div>
                )}
                <div className="dashboard-action-list">
                  {weeklyReport.recommendations.slice(0, 3).map(item => (
                    <ActionRow key={item} title="周报建议" desc={item} action="查看岗位" onClick={() => onNavigate?.("jobs")} />
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="dashboard-ops-grid" style={{ order: Math.min(panelOrder("workflow"), panelOrder("timeline")), display: (!panelVisible("workflow") && !panelVisible("timeline")) ? "none" : undefined }}>
            {panelVisible("workflow") && (
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">任务中心</div>
                    <p className="capture-panel-copy">集中查看运行、失败和可恢复任务。</p>
                  </div>
                  {workflowCenter && <span className="tag tag--muted">可重试 {workflowCenter.summary.retryable}</span>}
                </div>
                {workflowCenter ? (
                  <>
                    <div className="task-center-summary">
                      <span>运行 {workflowCenter.summary.running}</span>
                      <span>失败 {workflowCenter.summary.failed}</span>
                      <span>完成 {workflowCenter.summary.completed}</span>
                    </div>
                    {workflowCenter.recoveryGroups.length > 0 && (
                      <div className="task-recovery-groups">
                        {workflowCenter.recoveryGroups.slice(0, 4).map(group => (
                          <div key={group.category} className="task-recovery-group">
                            <strong>{group.label}</strong>
                            <span>{group.count} 个 · 可重试 {group.retryable}</span>
                            <p>{group.action}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    {workflowCenter.recoveryActions?.length ? (
                      <div className="task-recovery-actions">
                        {workflowCenter.recoveryActions.slice(0, 4).map(action => (
                          <button type="button" key={action.category} className={action.primary ? "button-primary button-secondary--sm" : "button-secondary button-secondary--sm"} onClick={() => onNavigate?.(action.page)}>
                            {action.label} · {action.count}
                          </button>
                        ))}
                      </div>
                    ) : null}
                    <div className="task-center-list">
                      {[...workflowCenter.running, ...workflowCenter.recovery].slice(0, 5).map(task => (
                        <div key={task.id} className={`task-center-item task-center-item--${task.status}`}>
                          <strong>{task.title}</strong>
                          <p>{task.message || task.action || task.type}</p>
                          <span>{task.status}{task.total ? ` · ${task.done}/${task.total}` : ""}</span>
                        </div>
                      ))}
                      {workflowCenter.running.length + workflowCenter.recovery.length === 0 && <p className="assistant-empty">暂无运行或失败任务。</p>}
                    </div>
                  </>
                ) : (
                  <p className="assistant-empty">任务中心加载中。</p>
                )}
              </div>
            </div>
            )}

            {panelVisible("timeline") && (
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">投递时间线</div>
                    <p className="capture-panel-copy">最近状态变化会在这里沉淀，便于跟进。</p>
                  </div>
                  {timeline && <span className="tag tag--muted">记录 {timeline.total}</span>}
                </div>
                {timeline && timeline.events.length > 0 ? (
                  <div className="application-timeline">
                    {timeline.events.slice(0, 5).map(event => (
                      <button type="button" key={`${event.jobId}-${event.at}-${event.status}`} className="application-timeline-item" onClick={() => onNavigate?.("jobs")}>
                        <strong>{event.company} · {event.title}</strong>
                        <p>{applicationStatusLabel(event.status)}{event.note ? ` · ${event.note}` : ""}</p>
                        <time>{event.at.slice(0, 19).replace("T", " ")}</time>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="assistant-empty">暂无投递状态变化。更新岗位求职状态后会自动出现。</p>
                )}
              </div>
            </div>
            )}
          </div>

          <div className="assistant-grid" style={{ order: Math.min(panelOrder("assistant"), panelOrder("followups"), panelOrder("promptVersions")), display: (!panelVisible("assistant") && !panelVisible("followups") && !panelVisible("promptVersions")) ? "none" : undefined }}>
            {panelVisible("assistant") && (
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">智能求职助理</div>
                    <p className="capture-panel-copy">
                      {focusJob ? `当前分析：${focusJob.title} · ${focusJob.company}` : "暂无岗位可分析"}
                    </p>
                  </div>
                  <button type="button" className="button-primary" disabled={!focusJob || assistantLoading} onClick={runAssistant}>
                    {assistantLoading ? "生成中..." : "生成助理建议"}
                  </button>
                </div>
                {assistant.strategy ? (
                  <div className="assistant-result-grid">
                    <AssistantBlock title={`投递策略：${assistant.strategy.label}`} items={[...assistant.strategy.reasons, ...assistant.strategy.nextActions]} tone="accent" />
                    {assistant.jdQuality && <AssistantBlock title={`JD 质量：${assistant.jdQuality.qualityScore} 分`} items={[...assistant.jdQuality.signals, ...assistant.jdQuality.cleaningAdvice]} tone={assistant.jdQuality.noiseLevel === "high" ? "danger" : "muted"} />}
                    {assistant.rewrite && <AssistantBlock title="简历反推建议" items={[...assistant.rewrite.rewriteFocus, ...assistant.rewrite.bulletSuggestions]} tone="green" />}
                    {assistant.interview && <AssistantBlock title="面试准备" items={[assistant.interview.companyBrief, ...assistant.interview.questions.slice(0, 3), ...assistant.interview.reverseQuestions.slice(0, 2)]} tone="muted" />}
                    {assistant.risk && <AssistantBlock title={`风险解释：${assistant.risk.riskLevel}`} items={[assistant.risk.plainLanguage, ...assistant.risk.impact, ...assistant.risk.questionsToAsk.slice(0, 2)]} tone={assistant.risk.riskLevel === "high" ? "danger" : "muted"} />}
                    {deepReport && focusJob && (
                      <div className="assistant-block assistant-block--accent assistant-block--wide">
                        <strong>深度报告</strong>
                        <AiFeedbackButtons
                          domain="deep_report"
                          targetId={focusJob.id}
                          compact
                          context={{ company: focusJob.company, title: focusJob.title }}
                        />
                        <div className="assistant-report-actions">
                          <a className="button-secondary button-secondary--sm" href={exportAssistantDeepReportUrl(focusJob.id, "md")} download>导出 Markdown</a>
                          <a className="button-secondary button-secondary--sm" href={exportAssistantDeepReportUrl(focusJob.id, "json")} download>导出 JSON</a>
                          <a className="button-secondary button-secondary--sm" href={exportAssistantDeepReportUrl(focusJob.id, "pdf")} download>导出 PDF</a>
                        </div>
                        <textarea className="form-input" rows={3} value={reportSummary} onChange={e => setReportSummary(e.target.value)} placeholder="人工复核后补充总结" />
                        <div className="assistant-report-sections">
                          <label>
                            <span>策略</span>
                            <textarea className="form-input" rows={3} value={reportSections.strategy || ""} onChange={e => setReportSections(prev => ({ ...prev, strategy: e.target.value }))} placeholder="补充投递策略" />
                          </label>
                          <label>
                            <span>匹配</span>
                            <textarea className="form-input" rows={3} value={reportSections.match || ""} onChange={e => setReportSections(prev => ({ ...prev, match: e.target.value }))} placeholder="补充 JD 与简历匹配判断" />
                          </label>
                          <label>
                            <span>风险</span>
                            <textarea className="form-input" rows={3} value={reportSections.risk || ""} onChange={e => setReportSections(prev => ({ ...prev, risk: e.target.value }))} placeholder="补充风险说明" />
                          </label>
                          <label>
                            <span>面试</span>
                            <textarea className="form-input" rows={3} value={reportSections.interview || ""} onChange={e => setReportSections(prev => ({ ...prev, interview: e.target.value }))} placeholder="补充面试准备" />
                          </label>
                          <label className="assistant-report-sections__wide">
                            <span>行动</span>
                            <textarea className="form-input" rows={3} value={reportSections.actions || ""} onChange={e => setReportSections(prev => ({ ...prev, actions: e.target.value }))} placeholder="补充下一步行动" />
                          </label>
                        </div>
                        <button type="button" className="button-primary button-secondary--sm" onClick={saveReportEdit}>保存人工复核</button>
                        {reportStatus && <small>{reportStatus}</small>}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="assistant-empty">选择岗位后点击生成，系统会给出投递策略、JD 质量、简历改写、面试准备和风险追问。</p>
                )}
              </div>
            </div>
            )}

            {panelVisible("followups") && (
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-kicker">跟进提醒</div>
                {followups.length > 0 ? (
                  <div className="assistant-followup-list">
                    {followups.slice(0, 6).map(item => (
                      <div key={item.jobId} className={`assistant-followup assistant-followup--${item.priority}`}>
                        <strong>{item.company} · {item.title}</strong>
                        <p>{item.reason}</p>
                        <span>{item.suggestedAction}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="assistant-empty">暂无需要跟进的岗位。</p>
                )}
              </div>
            </div>
            )}

            {panelVisible("promptVersions") && (
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">AI 版本记录</div>
                    <p className="capture-panel-copy">记录实际 AI 调用的模型与提示词版本；不保存岗位原文、简历或个人信息。</p>
                  </div>
                  <div className="toolbar-strip">
                    <span className="tag tag--muted">记录 {promptVersions?.summary.total || 0}</span>
                    <button type="button" className="button-secondary button-secondary--sm" disabled={promptVersionsRefreshing} onClick={() => refreshPromptVersions()}>
                      {promptVersionsRefreshing ? "刷新中..." : "刷新"}
                    </button>
                    <button type="button" className="button-secondary button-secondary--sm" onClick={() => setPromptVersionsCollapsed(prev => !prev)}>
                      {promptVersionsCollapsed ? "展开" : "折叠"}
                    </button>
                    <button type="button" className="button-quiet button-danger" disabled={!promptVersions?.versions.length} onClick={onClearPromptVersions}>
                      清空
                    </button>
                  </div>
                </div>
                {!promptVersionsCollapsed && promptVersions && promptVersions.versions.length > 0 ? (
                  <div className="prompt-version-list">
                    {promptVersions.versions.slice(0, 5).map(item => (
                      <div key={item.id} className="prompt-version-item">
                        <strong>{item.company || "通用 AI 调用"}{item.title ? ` · ${item.title}` : ""}</strong>
                        <span>{item.kind} · {item.promptVersion} · 偏好信号 {item.payloadSummary.preferenceSignals}</span>
                        <p>{item.feedbackGuidance.recentNotes?.[0] || item.promptPreview}</p>
                        <time>{item.createdAt.replace("T", " ").slice(0, 19)}</time>
                        <div className="prompt-version-item__actions">
                          {item.kind === "deep_report" && <button type="button" className="button-secondary button-secondary--sm" onClick={() => loadPromptCompare(item.jobId)}>对比版本</button>}
                          <button type="button" className="button-quiet button-danger" onClick={() => onDeletePromptVersion(item.id)}>删除</button>
                        </div>
                      </div>
                    ))}
                    {promptVersions.versions.length > 5 && (
                      <p className="assistant-empty">已收起其余 {promptVersions.versions.length - 5} 条，清理后可减少展示噪音。</p>
                    )}
                  </div>
                ) : promptVersionsCollapsed ? (
                  <p className="assistant-empty">版本记录已折叠，点击展开查看最近记录。</p>
                ) : (
                  <p className="assistant-empty">暂无 AI 提示词版本记录。完成一次 AI 话术、JD 分析、排序或深度报告后会自动沉淀。</p>
                )}
                {!promptVersionsCollapsed && promptCompare && (
                  <div className="prompt-version-compare">
                    <strong>{promptCompare.summary.comparable ? "可对比" : "版本不足"}</strong>
                    <span>版本 {promptCompare.summary.totalVersions} · 偏好信号差 {promptCompare.differences.preferenceSignalDelta}</span>
                    <p>{promptCompare.differences.latestFeedbackNotes[0] || "暂无最新反馈备注"}</p>
                  </div>
                )}
              </div>
            </div>
            )}
          </div>

          {panelVisible("review") && reviewCenter && (
            <div ref={reviewPanelRef} className="panel panel-strong" style={{ order: panelOrder("review") }}>
              <div className="panel-inner">
                <div className="page-section__top">
                  <div>
                    <div className="page-kicker">复盘中心</div>
                    <p className="capture-panel-copy">根据触达、面试、拒绝和批次表现调整策略。</p>
                  </div>
                  <span className="tag tag--muted">批次 {reviewCenter.batches.length}</span>
                </div>
                <div className="dashboard-action-list">
                  {reviewCenter.recommendations.slice(0, 4).map(item => <ActionRow key={item} title="复盘建议" desc={item} action="查看岗位" onClick={() => onNavigate?.("jobs")} />)}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function stageLabel(stage: DashboardSummary["readiness"]["stage"]): string {
  const labels: Record<DashboardSummary["readiness"]["stage"], string> = {
    setup: "先完成基础配置",
    select_jobs: "先选择感兴趣的岗位",
    complete_jd: "先补齐岗位详情",
    diligence: "进入公司尽调",
    ranking: "生成综合排序",
    decision: "标记投递优先级",
    ready: "可以进入打招呼",
  };
  return labels[stage];
}

function blockerPage(key: string): "jobs" | "diligence" | "ranking" | "greeting" {
  if (key.includes("diligence")) return "diligence";
  if (key.includes("ranking")) return "ranking";
  if (key.includes("greeting")) return "greeting";
  return "jobs";
}

function applicationStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: "待处理",
    greeted: "已沟通",
    applied: "已投递",
    interviewing: "面试中",
    rejected: "已拒绝",
    abandoned: "已放弃",
  };
  return labels[status] || status;
}


function AssistantBlock({ title, items, tone }: { title: string; items: string[]; tone: "accent" | "green" | "danger" | "muted" }) {
  return (
    <div className={`assistant-block assistant-block--${tone}`}>
      <strong>{title}</strong>
      <ul>
        {items.filter(Boolean).slice(0, 6).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
      </ul>
    </div>
  );
}


function MetricCard({
  title,
  value,
  tone = "neutral",
  action,
  onClick,
}: {
  title: string;
  value: number;
  tone?: "neutral" | "ok" | "warn" | "danger";
  action: string;
  onClick?: () => void;
}) {
  return (
    <button type="button" className={`dashboard-metric dashboard-metric--${tone}`} onClick={onClick}>
      <span>{title}</span>
      <strong>{value}</strong>
      <em>{action}</em>
    </button>
  );
}


function ActionRow({ title, desc, action, onClick }: { title: string; desc: string; action: string; onClick?: () => void }) {
  return (
    <div className="dashboard-action-row">
      <div>
        <strong>{title}</strong>
        <p>{desc}</p>
      </div>
      <button type="button" className="button-secondary button-secondary--sm" onClick={onClick}>{action}</button>
    </div>
  );
}
