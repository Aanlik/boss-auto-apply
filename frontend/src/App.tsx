import { useEffect, useMemo, useState } from "react";
import { ACTIVE_PAGE_KEY, WorkflowProvider, useWorkflowState } from "./lib/store";
import { clearFailedWorkflowTasks, deleteWorkflowTask, getWorkflowHealthCheck, listJobPool, listWorkflowTasks, retryWorkflowTask } from "./lib/api";
import { buildRecoveryTasks, buildWorkflowTasks, buildWorkflowTodos } from "./lib/workflowInsights";
import type { JobPosting, WorkflowHealthCheck, WorkflowRuntimeTask } from "./lib/types";
import DashboardPage from "./pages/dashboard";
import ResumesPage from "./pages/resumes";
import JobsPage from "./pages/jobs";
import DiligencePage from "./pages/diligence";
import RankedJobsPage from "./pages/ranked-jobs";
import GreetingPage from "./pages/greeting";
import SettingsPanel from "./components/SettingsPanel";
import HelpCenter from "./components/HelpCenter";

type PageKey = "dashboard" | "resumes" | "jobs" | "diligence" | "ranking" | "greeting";

const pages: Array<{ key: PageKey; label: string }> = [
  { key: "dashboard", label: "仪表盘" },
  { key: "resumes", label: "简历" },
  { key: "jobs", label: "岗位" },
  { key: "diligence", label: "尽调" },
  { key: "ranking", label: "排序" },
  { key: "greeting", label: "打招呼" },
];

function getInitialPage(): PageKey {
  if (typeof window === "undefined") return "resumes";
  const saved = window.localStorage.getItem(ACTIVE_PAGE_KEY);
  if (pages.some(p => p.key === saved)) return saved as PageKey;
  return "dashboard";
}

function AppShell() {
  const [page, setPageState] = useState<PageKey>(getInitialPage);
  const [showSettings, setShowSettings] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const state = useWorkflowState();
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [runtimeTasks, setRuntimeTasks] = useState<WorkflowRuntimeTask[]>([]);
  const [healthCheck, setHealthCheck] = useState<WorkflowHealthCheck | null>(null);

  async function refreshJobsForWorkflow() {
    try {
      const result = await listJobPool();
      setJobs(result.jobs || []);
    } catch (err) {
      console.warn("[app] 加载全流程岗位状态失败:", err);
    }
  }

  async function refreshRuntimeTasks() {
    try {
      const result = await listWorkflowTasks();
      setRuntimeTasks(result.tasks || []);
    } catch (err) {
      console.warn("[app] 加载任务状态失败:", err);
    }
  }

  async function refreshHealthCheck() {
    try {
      setHealthCheck(await getWorkflowHealthCheck());
    } catch (err) {
      console.warn("[app] 加载系统健康状态失败:", err);
    }
  }

  async function refreshGlobalStatus() {
    await Promise.all([refreshJobsForWorkflow(), refreshRuntimeTasks(), refreshHealthCheck()]);
  }

  useEffect(() => {
    refreshGlobalStatus();
    const timer = window.setInterval(refreshGlobalStatus, 10000);
    const onFocus = () => refreshGlobalStatus();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  useEffect(() => {
    refreshGlobalStatus();
  }, [page]);

  function setPage(pageKey: PageKey) {
    setPageState(pageKey);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ACTIVE_PAGE_KEY, pageKey);
    }
  }

  function navigateFromDashboard(pageKey: string) {
    if (pageKey === "settings") {
      setShowSettings(true);
      return;
    }
    if (pages.some(item => item.key === pageKey)) {
      setPage(pageKey as PageKey);
    }
  }

  function navigateFromHelp(pageKey: string) {
    if (pageKey === "settings") {
      setShowSettings(true);
      return;
    }
    if (pages.some(item => item.key === pageKey)) {
      setPage(pageKey as PageKey);
    }
  }

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <span className="app-logo">
          <img src="/assets/boss-helper-logo-64.png" alt="" aria-hidden="true" />
          boss 求职助手
        </span>
        <div className="nav-links">
          {pages.map(p => (
            <button key={p.key} className={`nav-link ${page === p.key ? "nav-link--active" : ""}`}
              onClick={() => {
                setPage(p.key);
              }}>
              {p.label}
              {p.key === "jobs" && state.selectedJobIds.length > 0 && (
                <span className="nav-badge">{state.selectedJobIds.length}</span>
              )}
            </button>
          ))}
        </div>
        <button
          className={`nav-link ${showSettings ? "nav-link--active" : ""}`}
          onClick={() => setShowSettings(!showSettings)}
        >
          ⚙ 设置
        </button>
        <button
          className={`nav-link ${showHelp ? "nav-link--active" : ""}`}
          onClick={() => setShowHelp(!showHelp)}
        >
          帮助
        </button>
      </nav>

      <SettingsPanel show={showSettings} onClose={() => setShowSettings(false)} />
      <HelpCenter show={showHelp} onClose={() => setShowHelp(false)} onNavigate={navigateFromHelp} />
      <GlobalWorkflowStatus jobs={jobs} runtimeTasks={runtimeTasks} healthCheck={healthCheck} onRefresh={refreshGlobalStatus} onNavigate={setPage} />

      <main className="workspace-stage">
        <div style={{ display: page === "dashboard" ? "block" : "none" }}>
          <DashboardPage onNavigate={navigateFromDashboard} />
        </div>
        <div style={{ display: page === "resumes" ? "block" : "none" }}>
          <ResumesPage />
        </div>
        <div style={{ display: page === "jobs" ? "block" : "none" }}>
          <JobsPage onNavigate={(p) => setPage(p as PageKey)} visible={page === "jobs"} />
        </div>
        <div style={{ display: page === "diligence" ? "block" : "none" }}>
          <DiligencePage onNavigate={(p) => setPage(p as PageKey)} />
        </div>
        <div style={{ display: page === "ranking" ? "block" : "none" }}>
          <RankedJobsPage onNavigate={(p) => setPage(p as PageKey)} />
        </div>
        <div style={{ display: page === "greeting" ? "block" : "none" }}>
          <GreetingPage />
        </div>
      </main>
    </div>
  );
}

function GlobalWorkflowStatus({
  jobs,
  runtimeTasks,
  healthCheck,
  onRefresh,
  onNavigate,
}: {
  jobs: JobPosting[];
  runtimeTasks: WorkflowRuntimeTask[];
  healthCheck: WorkflowHealthCheck | null;
  onRefresh: () => void;
  onNavigate: (page: PageKey) => void;
}) {
  const state = useWorkflowState();
  const tasks = useMemo(() => buildWorkflowTasks({
    jobs,
    selectedJobIds: state.selectedJobIds,
    greetingJobIds: state.greetingJobIds,
    diligenceReports: state.diligenceReports,
    rankingResults: state.rankingResults,
    greetingTexts: state.greetingTexts,
  }), [jobs, state.selectedJobIds, state.greetingJobIds, state.diligenceReports, state.rankingResults, state.greetingTexts]);

  const activeRuntimeTasks = runtimeTasks.filter(task => task.status === "running" || task.status === "queued").slice(0, 2);
  const recoveryTasks = useMemo(() => buildRecoveryTasks(runtimeTasks).slice(0, 3), [runtimeTasks]);
  const attentionChecks = (healthCheck?.checks || []).filter(item => item.status !== "ok").slice(0, 3);
  const todos = useMemo(() => buildWorkflowTodos({
    jobs,
    selectedJobIds: state.selectedJobIds,
    greetingJobIds: state.greetingJobIds,
    diligenceReports: state.diligenceReports,
    rankingResults: state.rankingResults,
    greetingTexts: state.greetingTexts,
  }).slice(0, 3), [jobs, state.selectedJobIds, state.greetingJobIds, state.diligenceReports, state.rankingResults, state.greetingTexts]);
  const hasRuntimePanel = activeRuntimeTasks.length > 0 || recoveryTasks.length > 0 || todos.length > 0 || attentionChecks.length > 0;
  const hasBusinessTodos = todos.length > 0;
  const workflowStatusCopy = healthCheck?.status === "error"
    ? "服务异常"
    : healthCheck?.status === "ok"
      ? (hasBusinessTodos ? "服务正常 · 业务待推进" : "服务正常 · 流程已完成")
      : "服务需关注";

  function targetPage(taskType: string): PageKey {
    if (taskType.includes("diligence")) return "diligence";
    if (taskType.includes("ranking")) return "ranking";
    if (taskType.includes("greeting")) return "greeting";
    return "jobs";
  }

  async function retryTask(taskId: string) {
    try {
      await retryWorkflowTask(taskId);
      onRefresh();
    } catch (err) {
      console.warn("[app] 任务重试失败:", err);
      window.alert(err instanceof Error ? err.message : "任务重试失败");
    }
  }

  async function clearRecoveryTasks() {
    if (!window.confirm("确定清空失败恢复中心里的失败任务吗？运行中和已完成任务会保留。")) return;
    try {
      await clearFailedWorkflowTasks();
      onRefresh();
    } catch (err) {
      console.warn("[app] 清空失败任务失败:", err);
      window.alert(err instanceof Error ? err.message : "清空失败任务失败");
    }
  }

  async function removeTask(taskId: string, title: string) {
    if (!window.confirm(`确定删除任务「${title}」吗？`)) return;
    try {
      await deleteWorkflowTask(taskId);
      onRefresh();
    } catch (err) {
      console.warn("[app] 删除任务失败:", err);
      window.alert(err instanceof Error ? err.message : "删除任务失败");
    }
  }

  return (
    <section className="global-workflow-status" aria-label="全流程状态">
      <div className={`global-workflow-status__inner${hasRuntimePanel ? " global-workflow-status__inner--with-recovery" : ""}`}>
        <div className="global-workflow-status__title">
          <span>全流程状态</span>
          <small>岗位池到打招呼 · {workflowStatusCopy}</small>
        </div>
        {healthCheck && (
          <div className={`health-pill health-pill--${healthCheck.status}`}>
            {healthCheck.status === "ok" ? "健康" : healthCheck.status === "error" ? "异常" : "需关注"}
          </div>
        )}
        <div className="workflow-status-grid workflow-status-grid--compact">
          {tasks.map(task => (
            <div key={task.key} className={`workflow-status-card workflow-status-card--${task.status}`}>
              <div className="workflow-status-card__top">
                <span>{task.label}</span>
                <strong>{task.done}/{task.total}</strong>
              </div>
              <div className="workflow-meter" aria-hidden="true">
                <span style={{ width: `${task.total > 0 ? Math.min(100, Math.round((task.done / task.total) * 100)) : 0}%` }} />
              </div>
            </div>
          ))}
        </div>
        {hasRuntimePanel && (
          <div className="workflow-recovery-panel" aria-label="流程操作中心">
            <div className="workflow-recovery-panel__top">
              <strong>{recoveryTasks.length > 0 ? "失败恢复中心" : activeRuntimeTasks.length > 0 ? "任务执行中" : attentionChecks.length > 0 ? "系统检查" : "今日待办"}</strong>
              <div className="workflow-recovery-panel__actions">
                {recoveryTasks.length > 0 && (
                  <button type="button" className="button-quiet button-compact button-danger" onClick={clearRecoveryTasks}>清空失败任务</button>
                )}
                <button type="button" className="button-quiet button-compact" onClick={onRefresh}>刷新状态</button>
              </div>
            </div>
            {attentionChecks.map(check => (
              <div key={check.key} className={`workflow-recovery-item workflow-recovery-item--${check.status}`}>
                <span>{check.label}</span>
                <small>{check.message}</small>
                {check.action && <em>{check.action}</em>}
              </div>
            ))}
            {activeRuntimeTasks.map(task => (
              <div key={task.id} className={`workflow-recovery-item workflow-recovery-item--${task.status}`}>
                <span>{task.title}</span>
                <small>{task.message || "正在处理..."}</small>
                {task.status === "queued" && (
                  <button type="button" className="button-quiet button-secondary--sm button-danger" onClick={() => removeTask(task.id, task.title)}>
                    删除
                  </button>
                )}
              </div>
            ))}
            {recoveryTasks.map(task => {
              const sourceTask = runtimeTasks.find(item => item.id === task.id);
              return (
                <div key={task.id} className="workflow-recovery-item">
                  <span>{task.title}</span>
                  <small>{task.message}</small>
                  <em>{task.action}</em>
                  {sourceTask && (
                    <>
                      <button type="button" className="button-secondary button-secondary--sm" onClick={() => retryTask(sourceTask.id)}>
                        重试
                      </button>
                      <button type="button" className="button-quiet button-secondary--sm" onClick={() => onNavigate(targetPage(sourceTask.type))}>
                        处理
                      </button>
                      <button type="button" className="button-quiet button-secondary--sm button-danger" onClick={() => removeTask(sourceTask.id, sourceTask.title)}>
                        删除
                      </button>
                    </>
                  )}
                </div>
              );
            })}
            {todos.map(todo => (
              <div key={todo.key} className="workflow-recovery-item workflow-todo-item">
                <span>{todo.label}</span>
                <small>{todo.description}</small>
                <em>{todo.count} 项</em>
                <button type="button" className="button-secondary button-secondary--sm" onClick={() => onNavigate(todo.page)}>
                  {todo.action}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

export default function App() {
  return (
    <WorkflowProvider>
      <AppShell />
    </WorkflowProvider>
  );
}
