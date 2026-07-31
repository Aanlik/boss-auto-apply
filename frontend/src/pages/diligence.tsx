import { useState, useEffect, useMemo, useRef } from "react";
import { listJobPool as poolJobs, analyzeJD, evaluateCompany, getDiligenceReports, refreshDiligence, saveDiligenceNote, exportDiligenceUrl } from "../lib/api";
import type { DiligenceReport, JobPosting } from "../lib/types";
import { useWorkflowState, useWorkflowDispatch, actions } from "../lib/store";
import ChatPanel from "../components/ChatPanel";
import { EmptyState, ErrorBanner } from "../components/SharedUI";
import { buildDiligenceEvidence } from "../lib/workflowInsights";
import AiFeedbackButtons from "../components/AiFeedbackButtons";
import { resolveDiligencePrimaryAction, resolveJdAnalysisAction } from "../lib/diligenceActions";

type CardState = { jdExpanded: boolean; ddExpanded: boolean; chatExpanded: boolean };
type BatchProgress = { kind: "jd" | "dd"; done: number; total: number; current: string } | null;

export default function DiligencePage({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const { selectedJobIds, jdAnalyses, diligenceReports, chatMessages } = useWorkflowState();
  const dispatch = useWorkflowDispatch();

  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [localSelection, setLocalSelection] = useState<string[]>(() => [...selectedJobIds]);
  const [cardStates, setCardStates] = useState<Record<string, CardState>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [batchProgress, setBatchProgress] = useState<BatchProgress>(null);
  const [error, setError] = useState("");

  // useRef 追踪最新累积数据，避免闭包过期导致覆盖
  const jdAnalysesRef = useRef(jdAnalyses);
  jdAnalysesRef.current = jdAnalyses;
  const diligenceRef = useRef(diligenceReports);
  diligenceRef.current = diligenceReports;

  // 同步外部选择
  useEffect(() => { setLocalSelection([...selectedJobIds]); }, [selectedJobIds]);

  useEffect(() => {
    getDiligenceReports()
      .then(r => {
        if (r.reports && Object.keys(r.reports).length > 0) {
          dispatch(actions.setDiligenceReports({ ...diligenceRef.current, ...r.reports }));
        }
      })
      .catch(() => {});
  }, [dispatch]);

  // 加载岗位，同时清空之前的尽调缓存
  useEffect(() => {
    poolJobs().then(r => {
      const all = r.jobs || [];
      const selected = all.filter((j: JobPosting) => selectedJobIds.includes(j.id));
      setJobs(selected);
      const savedAnalyses = selected.reduce<Record<string, NonNullable<JobPosting["jd_analysis"]>>>((acc, job: JobPosting) => {
        if (job.jd_analysis) acc[job.id] = job.jd_analysis;
        return acc;
      }, {});
      if (Object.keys(savedAnalyses).length > 0) {
        dispatch(actions.setJdAnalyses({ ...savedAnalyses, ...jdAnalysesRef.current }));
      }
      const removedFromSelection = selectedJobIds.filter(id => !selected.some(j => j.id === id));
      if (removedFromSelection.length > 0) {
        dispatch(actions.setSelection(selected.map(j => j.id)));
        setError(prev => prev || `已自动同步选择：${removedFromSelection.length} 个岗位因黑名单或下架被移除`);
      }
    }).catch((err) => {
      console.warn("[diligence] 加载岗位失败:", err);
    });
  }, [selectedJobIds, dispatch]);

  function toggleLocal(id: string) {
    setLocalSelection(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }
  function selectAllLocal() { setLocalSelection(jobs.map(j => j.id)); }
  function clearLocal() { setLocalSelection([]); }

  function toggleCard(jobId: string, key: keyof CardState) {
    setCardStates(prev => {
      const cur = prev[jobId] || { jdExpanded: false, ddExpanded: false, chatExpanded: false };
      return { ...prev, [jobId]: { ...cur, [key]: !cur[key] } };
    });
  }

  const diligenceIndex = useMemo(() => {
    const index: Record<string, DiligenceReport> = {};
    Object.entries(diligenceReports).forEach(([key, report]) => {
      if (!report) return;
      const businessInfo = report.businessInfo;
      [key, report.companyName, report.sourceCompanyName, report.companyKey, businessInfo?.companyName, businessInfo?.sourceCompanyName, businessInfo?.companyKey, businessInfo?.unifiedCreditCode]
        .filter(Boolean)
        .forEach(value => { index[String(value).trim()] = report; });
    });
    return index;
  }, [diligenceReports]);

  function diligenceForJob(job: JobPosting) {
    return (job.company_key && diligenceIndex[job.company_key]) || diligenceIndex[job.company] || null;
  }

  function withDiligenceReport(job: JobPosting, report: DiligenceReport) {
    const next = { ...diligenceRef.current };
    const canonicalKey = report.companyName || job.company;
    next[canonicalKey] = report;
    if (report.sourceCompanyName && report.sourceCompanyName !== canonicalKey) delete next[report.sourceCompanyName];
    if (job.company !== canonicalKey) delete next[job.company];
    return next;
  }

  // ── JD 分析（单条）──
  async function onAnalyzeJD(job: JobPosting) {
    setLoading(prev => ({ ...prev, [job.id]: true })); setError("");
    try {
      const data = await analyzeJD({ job_id: job.id, title: job.title, company: job.company, jd_text: job.jd_text });
      // 使用 ref 拿到最新累积数据，防止覆盖其他已完成的分析
      dispatch(actions.setJdAnalyses({ ...jdAnalysesRef.current, [job.id]: data }));
      setCardStates(prev => {
        const cur = prev[job.id] || { jdExpanded: false, ddExpanded: false, chatExpanded: false };
        return { ...prev, [job.id]: { ...cur, jdExpanded: true } };
      });
    } catch (err) { setError(err instanceof Error ? err.message : "JD分析失败"); }
    finally { setLoading(prev => ({ ...prev, [job.id]: false })); }
  }

  // ── 一键 JD 分析 ──
  async function analyzeSelectedJD(targetIds?: string[]) {
    // 先收集本地累积结果
    const accumulated = { ...jdAnalysesRef.current };
    const explicitTargets = targetIds ? new Set(targetIds) : null;
    const targets = jobs.filter(job => explicitTargets ? explicitTargets.has(job.id) : localSelection.includes(job.id) && !accumulated[job.id]);
    if (targets.length === 0) return;
    setBatchProgress({ kind: "jd", done: 0, total: targets.length, current: targets[0].title });
    for (const job of targets) {
      setLoading(prev => ({ ...prev, [job.id]: true }));
      setBatchProgress(prev => prev ? { ...prev, current: job.title } : prev);
      try {
        const data = await analyzeJD({ job_id: job.id, title: job.title, company: job.company, jd_text: job.jd_text });
        accumulated[job.id] = data;
        // 每完成一个立即写到 store
        dispatch(actions.setJdAnalyses({ ...accumulated }));
      } catch (err) {
        setError(err instanceof Error ? err.message : `JD分析失败: ${job.title}`);
      }
      setLoading(prev => ({ ...prev, [job.id]: false }));
      setBatchProgress(prev => prev ? { ...prev, done: prev.done + 1 } : prev);
    }
    dispatch(actions.setJdAnalyses({ ...accumulated }));
    setBatchProgress(null);
  }

  // ── 公司尽调（单条）──
  async function onCompanyDiligence(job: JobPosting) {
    setLoading(prev => ({ ...prev, [job.id + "-dd"]: true })); setError("");
    try {
      const report = await evaluateCompany({
        company_name: job.company, job_title: job.title,
        jd_text: job.jd_text, jd_analysis: jdAnalysesRef.current[job.id] || null,
      });
      dispatch(actions.setDiligenceReports(withDiligenceReport(job, report)));
      setCardStates(prev => {
        const cur = prev[job.id] || { jdExpanded: false, ddExpanded: false, chatExpanded: false };
        return { ...prev, [job.id]: { ...cur, ddExpanded: true } };
      });
    } catch (err) { setError(err instanceof Error ? err.message : "尽调失败"); }
    finally { setLoading(prev => ({ ...prev, [job.id + "-dd"]: false })); }
  }

  async function onRefreshDiligence(job: JobPosting, mode: "full" | "business" | "search") {
    setLoading(prev => ({ ...prev, [job.id + "-refresh-" + mode]: true }));
    setError("");
    try {
      const report = await refreshDiligence({
        company_name: diligenceForJob(job)?.companyKey || diligenceForJob(job)?.companyName || job.company,
        mode,
        job_title: job.title,
        jd_text: job.jd_text,
        jd_analysis: jdAnalysesRef.current[job.id] || null,
      });
      dispatch(actions.setDiligenceReports(withDiligenceReport(job, report)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "刷新尽调失败");
    } finally {
      setLoading(prev => ({ ...prev, [job.id + "-refresh-" + mode]: false }));
    }
  }

  // ── 一键尽调 ──
  async function diligenceSelected(targetIds?: string[]) {
    const accumulatedReports = { ...diligenceRef.current };
    const explicitTargets = targetIds ? new Set(targetIds) : null;
    const targets = jobs.filter(job => explicitTargets ? explicitTargets.has(job.id) : localSelection.includes(job.id) && !diligenceForJob(job));
    if (targets.length === 0) return;
    setBatchProgress({ kind: "dd", done: 0, total: targets.length, current: targets[0].company });
    for (const job of targets) {
      setLoading(prev => ({ ...prev, [job.id + "-dd"]: true }));
      setBatchProgress(prev => prev ? { ...prev, current: job.company } : prev);
      try {
        const report = await evaluateCompany({
          company_name: job.company, job_title: job.title,
          jd_text: job.jd_text, jd_analysis: jdAnalysesRef.current[job.id] || null,
        });
        const canonicalKey = report.companyName || job.company;
        accumulatedReports[canonicalKey] = report;
        if (report.sourceCompanyName && report.sourceCompanyName !== canonicalKey) delete accumulatedReports[report.sourceCompanyName];
        if (job.company !== canonicalKey) delete accumulatedReports[job.company];
        dispatch(actions.setDiligenceReports({ ...accumulatedReports }));
      } catch (err) {
        setError(err instanceof Error ? err.message : `尽调失败: ${job.company}`);
      }
      setLoading(prev => ({ ...prev, [job.id + "-dd"]: false }));
      setBatchProgress(prev => prev ? { ...prev, done: prev.done + 1 } : prev);
    }
    dispatch(actions.setDiligenceReports({ ...accumulatedReports }));
    setBatchProgress(null);
  }

  const uniqueCompanies = useMemo(
    () => [...new Map(jobs.map(j => [j.company, j])).values()],
    [jobs]
  );

  const primaryAction = useMemo(() => resolveDiligencePrimaryAction({
    jobs,
    selectedJobIds: localSelection,
    jdAnalyses,
    diligenceReports,
  }), [jobs, localSelection, jdAnalyses, diligenceReports]);
  const jdAction = useMemo(() => resolveJdAnalysisAction({
    jobs,
    selectedJobIds: localSelection,
    jdAnalyses,
  }), [jobs, localSelection, jdAnalyses]);
  const primaryActionBusy = batchProgress !== null || primaryAction.targetIds.some(id => loading[id] || loading[id + "-dd"]);
  const jdActionBusy = batchProgress?.kind === "jd" || jdAction.targetIds.some(id => loading[id]);

  async function runPrimaryAction() {
    if (primaryAction.disabled || primaryActionBusy) return;
    if (primaryAction.kind === "analyze_jd") {
      await analyzeSelectedJD(primaryAction.targetIds);
    } else if (primaryAction.kind === "diligence" || primaryAction.kind === "rediligence") {
      await diligenceSelected(primaryAction.targetIds);
    }
  }

  function primaryActionForJob(job: JobPosting) {
    return resolveDiligencePrimaryAction({
      jobs: [job],
      selectedJobIds: [job.id],
      jdAnalyses,
      diligenceReports,
    });
  }

  async function runPrimaryActionForJob(job: JobPosting) {
    const action = primaryActionForJob(job);
    if (action.kind === "analyze_jd") {
      await onAnalyzeJD(job);
    } else if (action.kind === "diligence" || action.kind === "rediligence") {
      await onCompanyDiligence(job);
    }
  }

  function goToRanking() {
    if (localSelection.length === 0) return;
    dispatch(actions.setSelection([...localSelection]));
    onNavigate?.("ranking");
  }

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">公司尽调</p>
          <h2 className="page-title">公司尽调 & JD 分析</h2>
          <p className="page-copy">千帆智能搜索 + AI 总结 → AI 整合分析，综合评估公司风险与前景。</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
	          <button type="button" className="button-primary" onClick={() => analyzeSelectedJD(jdAction.targetIds)}
	            disabled={jdAction.disabled || jdActionBusy}>
	            {batchProgress?.kind === "jd" ? `JD分析 ${batchProgress.done}/${batchProgress.total}` : jdAction.label}
	          </button>
	          {primaryAction.kind !== "analyze_jd" && (
	          <button type="button" className="button-primary" onClick={runPrimaryAction}
	            disabled={primaryAction.disabled || primaryActionBusy}>
	            {batchProgress?.kind === "dd" ? `尽调 ${batchProgress.done}/${batchProgress.total}` : primaryAction.label}
	          </button>
	          )}
          {localSelection.length > 0 && (
            <button type="button" className="button-primary" onClick={goToRanking}
              style={{ background: "var(--accent-strong)" }}>
              进入排序 ({localSelection.length}) →
            </button>
          )}
        </div>
      </div>
      <div className="module-export-bar" aria-label="尽调数据导出">
        <span>尽调报告</span>
        <a className="button-secondary button-secondary--sm" href={exportDiligenceUrl("json")} download>导出 JSON</a>
        <a className="button-secondary button-secondary--sm" href={exportDiligenceUrl("csv")} download>导出 CSV</a>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}
      {batchProgress && (
        <div className="panel panel-strong">
          <div className="panel-inner">
            <div className="toolbar-strip">
              <span className="page-kicker" style={{ margin: 0 }}>
                {batchProgress.kind === "jd" ? "JD 分析进度" : "公司尽调进度"}
              </span>
              <span className="tag tag--active">{batchProgress.done}/{batchProgress.total}</span>
              <span className="text-muted" style={{ fontSize: 12 }}>当前：{batchProgress.current}</span>
            </div>
          </div>
        </div>
      )}

      {jobs.length > 0 && (
        <div className="panel panel-strong">
          <div className="panel-inner">
            <div className="toolbar-strip">
              <span className="page-kicker" style={{ margin: 0 }}>已选 {localSelection.length}/{jobs.length}</span>
              <button type="button" className="button-quiet" onClick={selectAllLocal}>全选</button>
              <button type="button" className="button-quiet" onClick={clearLocal}>清空</button>
            </div>
          </div>
        </div>
      )}

      {selectedJobIds.length === 0 && (
        <div className="panel panel-strong">
          <div className="panel-inner">
            <EmptyState icon="🔍" title="尚未选择岗位" desc="请在「岗位」页面勾选岗位后进入此页面。" />
          </div>
        </div>
      )}

      {jobs.map(job => {
        const analysis = jdAnalyses[job.id];
        const diligence = diligenceForJob(job);
        const evidence = diligence ? buildDiligenceEvidence(diligence) : null;
        const sel = localSelection.includes(job.id);
        const cs = cardStates[job.id] || { jdExpanded: false, ddExpanded: false, chatExpanded: false };
        const busyJd = loading[job.id];
        const busyDd = loading[job.id + "-dd"];
        const cardAction = primaryActionForJob(job);
        const cardBusy = busyJd || busyDd;

        return (
          <div key={job.id} className={`panel panel-strong${sel ? " job-card--selected" : ""}`}>
            <div className="panel-inner">
              <div className="page-section__top">
                <div style={{ display: "flex", alignItems: "flex-start", gap: 10, flex: 1, minWidth: 0 }}>
                  <input type="checkbox" checked={sel} onChange={() => toggleLocal(job.id)}
                    style={{ width: 16, height: 16, accentColor: "var(--accent)", marginTop: 3, flexShrink: 0 }} />
                  <div style={{ minWidth: 0 }}>
                    <strong style={{ fontSize: 15 }}>{job.title}</strong>
                    <p className="text-muted" style={{ fontSize: 13, marginTop: 2 }}>{job.company} · {job.city} · {job.salary}</p>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexShrink: 0 }}>
                  {diligence && (
                    <>
                      <div className="score-badge">
                        <div className="score-value" style={{
                          color: diligence.companyScore >= 70 ? "var(--success)" : diligence.companyScore >= 50 ? "#d97706" : "var(--danger)",
                          fontSize: 22,
                        }}>{diligence.companyScore || "—"}</div>
                        <span className="score-label">公司分</span>
                      </div>
                      <span className={`tag ${diligence.riskLevel === "low" ? "tag--green" : diligence.riskLevel === "medium" ? "" : "tag--red"}`}>
                        {diligence.riskLevel === "low" ? "低风险" : diligence.riskLevel === "medium" ? "中风险" : "高风险"}
                      </span>
                    </>
                  )}
                  <button type="button" className="button-primary button-secondary--sm"
                    disabled={cardAction.disabled || cardBusy} onClick={() => runPrimaryActionForJob(job)}>
                    {busyJd ? "分析中…" : busyDd ? "尽调中…" : cardAction.kind === "analyze_jd" ? "AI 分析 JD" : cardAction.kind === "diligence" ? "公司尽调" : "重新公司尽调"}
                  </button>
                  {diligence && (
                    <>
                      <button type="button" className="button-secondary button-secondary--sm"
                        disabled={!!loading[job.id + "-refresh-business"]}
                        onClick={() => onRefreshDiligence(job, "business")}>
                        {loading[job.id + "-refresh-business"] ? "工商刷新中…" : "刷新工商"}
                      </button>
                      <button type="button" className="button-secondary button-secondary--sm"
                        disabled={!!loading[job.id + "-refresh-search"]}
                        onClick={() => onRefreshDiligence(job, "search")}>
                        {loading[job.id + "-refresh-search"] ? "证据刷新中…" : "刷新证据"}
                      </button>
                      <button type="button" className="button-quiet button-secondary--sm"
                        disabled={!!loading[job.id + "-refresh-full"]}
                        onClick={() => onRefreshDiligence(job, "full")}>
                        {loading[job.id + "-refresh-full"] ? "全量刷新中…" : "全量刷新"}
                      </button>
                    </>
                  )}
                </div>
              </div>

              {analysis && (
                <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
                  <button type="button" className="button-quiet" onClick={() => toggleCard(job.id, "jdExpanded")}
                    style={{ fontSize: 13, fontWeight: 600 }}>
                    {cs.jdExpanded ? "▾" : "▸"} JD 分析结果
                  </button>
                  {cs.jdExpanded && (
                    <>
                      <div className="panel panel-muted" style={{ marginTop: 8 }}>
                        <div className="panel-inner" style={{ padding: "14px 18px" }}>
                          {analysis.must_have_skills?.length > 0 && (
                            <div style={{ marginBottom: 8 }}>
                              <span className="detail-label">必备技能</span>
                              <div className="job-tags" style={{ marginTop: 4 }}>
                                {analysis.must_have_skills.map((s: string, i: number) => <span key={i} className="tag tag--red">{s}</span>)}
                              </div>
                            </div>
                          )}
                          {analysis.nice_to_have_skills?.length > 0 && (
                            <div style={{ marginBottom: 8 }}>
                              <span className="detail-label">加分技能</span>
                              <div className="job-tags" style={{ marginTop: 4 }}>
                                {analysis.nice_to_have_skills.map((s: string, i: number) => <span key={i} className="tag tag--green">{s}</span>)}
                              </div>
                            </div>
                          )}
                          {analysis.experience_requirements?.length > 0 && (
                            <div style={{ marginBottom: 8 }}>
                              <span className="detail-label">经验要求</span>
                              <ul style={{ margin: "4px 0", paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                                {analysis.experience_requirements.map((s: string, i: number) => <li key={i}>{s}</li>)}
                              </ul>
                            </div>
                          )}
                          {analysis.soft_skills?.length > 0 && (
                            <div style={{ marginBottom: 8 }}>
                              <span className="detail-label">软技能</span>
                              <div className="job-tags" style={{ marginTop: 4 }}>
                                {analysis.soft_skills.map((s: string, i: number) => <span key={i} className="tag tag--muted">{s}</span>)}
                              </div>
                            </div>
                          )}
                          {analysis.domain_knowledge?.length > 0 && (
                            <div style={{ marginBottom: 8 }}>
                              <span className="detail-label">领域知识</span>
                              <div className="job-tags" style={{ marginTop: 4 }}>
                                {analysis.domain_knowledge.map((s: string, i: number) => <span key={i} className="tag">{s}</span>)}
                              </div>
                            </div>
                          )}
                          {analysis.education_requirements && (
                            <div style={{ marginBottom: 8 }}>
                              <span className="detail-label">学历要求</span>
                              <p style={{ fontSize: 12, marginTop: 2 }}>{analysis.education_requirements}</p>
                            </div>
                          )}
                          {analysis.summary_text && (
                            <div>
                              <span className="detail-label">分析总结</span>
                              <p style={{ fontSize: 12, marginTop: 2, lineHeight: 1.5 }}>{analysis.summary_text}</p>
                            </div>
                          )}
                          <AiFeedbackButtons
                            domain="jd_quality"
                            targetId={job.id}
                            compact
                            context={{ company: job.company, title: job.title }}
                          />
                        </div>
                      </div>
                      <div style={{ marginTop: 10 }}>
                        <ChatPanel chatKey={`dil-jd-${job.id}`} step="analyze" context={{ job_title: job.title, company: job.company, analysis }}
                          title="与 AI 讨论 JD 分析" placeholder="讨论 JD 分析结果…"
                          onApply={async (messages) => {
                            try {
                              const data = await analyzeJD({ job_id: job.id, title: job.title, company: job.company, jd_text: job.jd_text }, messages);
                              dispatch(actions.setJdAnalyses({ ...jdAnalysesRef.current, [job.id]: data }));
                              dispatch(actions.mergeChatMessage(job.id, messages));
                            } catch { setError("应用分析失败"); }
                          }} />
                      </div>
                    </>
                  )}
                </div>
              )}

              {diligence && (
                <div style={{ marginTop: analysis ? 8 : 12, paddingTop: analysis ? 8 : 12, borderTop: analysis ? "none" : "1px solid var(--border)" }}>
                  <button type="button" className="button-quiet" onClick={() => toggleCard(job.id, "ddExpanded")}
                    style={{ fontSize: 13, fontWeight: 600 }}>
                    {cs.ddExpanded ? "▾" : "▸"} 🏢 {diligence.companyName || job.company} 尽调报告
                  </button>
                  {cs.ddExpanded && (
                    <div className="panel panel-muted" style={{ marginTop: 8 }}>
                      <div className="panel-inner" style={{ padding: "14px 18px" }}>
                        {diligence.oneLiner && (
                          <p style={{ fontSize: 13, fontWeight: 600, color: "var(--accent-strong)", marginBottom: 10, lineHeight: 1.5 }}>
                            💡 {diligence.oneLiner}
                          </p>
                        )}
                        <AiFeedbackButtons
                          domain="diligence"
                          targetId={diligence.companyKey || diligence.companyName || job.company}
                          compact
                          context={{ company: diligence.companyName || job.company, score: diligence.companyScore, riskLevel: diligence.riskLevel }}
                        />
                        {evidence && (
                          <details className="evidence-panel" style={{ marginBottom: 12 }}>
                            <summary>证据来源与判断依据</summary>
                            <div className="evidence-trust-row" aria-label="证据可信度说明">
                              {evidence.sourceTrust.map(source => (
                                <div key={source.label} className={`evidence-trust evidence-trust--${source.level}`}>
                                  <strong>{source.label}</strong>
                                  <span>{source.description}</span>
                                </div>
                              ))}
                            </div>
                            <div className="evidence-grid">
                              <div>
                                <span className="detail-label">工商 API</span>
                                {evidence.business.length > 0 ? (
                                  <ul className="evidence-list">
                                    {evidence.business.map((item, i) => <li key={i}>{item}</li>)}
                                  </ul>
                                ) : <p className="evidence-empty">暂无可用工商证据</p>}
                              </div>
                              <div>
                                <span className="detail-label">风险记录</span>
                                {evidence.risk.length > 0 ? (
                                  <ul className="evidence-list evidence-list--risk">
                                    {evidence.risk.slice(0, 8).map((item, i) => <li key={i}>{item}</li>)}
                                  </ul>
                                ) : <p className="evidence-empty">未发现明确风险记录</p>}
                              </div>
                              <div>
                                <span className="detail-label">搜索证据</span>
                                {evidence.searchLinks.length > 0 ? (
                                  <div className="evidence-links">
                                    {evidence.searchLinks.slice(0, 8).map((link, i) => (
                                      <a key={i} href={link} target="_blank" rel="noopener noreferrer">{link}</a>
                                    ))}
                                  </div>
                                ) : <p className="evidence-empty">暂无搜索链接</p>}
                              </div>
                              <div>
                                <span className="detail-label">AI 信号</span>
                                {evidence.aiSignals.length > 0 ? (
                                  <ul className="evidence-list">
                                    {evidence.aiSignals.slice(0, 8).map((item, i) => <li key={i}>{item}</li>)}
                                  </ul>
                                ) : <p className="evidence-empty">暂无 AI 归纳信号</p>}
                              </div>
                            </div>
                          </details>
                        )}
                        {diligence.basicInfo && (
                          <div style={{ marginBottom: 10 }}>
                            <span className="detail-label">基本信息</span>
                            <div style={{ fontSize: 12, marginTop: 3, display: "flex", flexWrap: "wrap", gap: "4px 14px" }}>
                              <span>规模: <strong>{diligence.basicInfo.scale || "—"}</strong></span>
                              <span>融资: <strong>{diligence.basicInfo.funding || "—"}</strong></span>
                              <span>成立: <strong>{diligence.basicInfo.founded || "—"}</strong></span>
                            </div>
                            <p style={{ fontSize: 12, marginTop: 2 }}>业务: {diligence.basicInfo.business || "—"}</p>
                          </div>
                        )}

                        {diligence.businessInfo && !diligence.businessInfo.error && (
                          <div style={{ marginBottom: 10 }}>
                            <span className="detail-label">🏛️ 工商信息</span>
                            <div style={{ fontSize: 12, marginTop: 3, display: "flex", flexWrap: "wrap", gap: "4px 14px" }}>
                              {diligence.businessInfo.legalRepresentative && <span>法人: <strong>{diligence.businessInfo.legalRepresentative}</strong></span>}
                              {diligence.businessInfo.registrationCapital && <span>注册资本: <strong>{diligence.businessInfo.registrationCapital}</strong></span>}
                              {diligence.businessInfo.establishedDate && <span>成立日期: <strong>{diligence.businessInfo.establishedDate}</strong></span>}
                              {diligence.businessInfo.businessStatus && <span>状态: <strong>{diligence.businessInfo.businessStatus}</strong></span>}
                              {diligence.businessInfo.unifiedCreditCode && <span>信用代码: <strong>{diligence.businessInfo.unifiedCreditCode}</strong></span>}
                              {diligence.businessInfo.companyType && <span>类型: <strong>{diligence.businessInfo.companyType}</strong></span>}
                              {diligence.businessInfo.industry && <span>行业: <strong>{diligence.businessInfo.industry}{diligence.businessInfo.subIndustry ? ` / ${diligence.businessInfo.subIndustry}` : ""}</strong></span>}
                              {diligence.businessInfo.registrationAuthority && <span>登记机关: <strong>{diligence.businessInfo.registrationAuthority}</strong></span>}
                              {diligence.businessInfo.branchCount > 0 && <span>分支机构: <strong>{diligence.businessInfo.branchCount}</strong></span>}
                              {diligence.businessInfo.changeCount ? <span>变更: <strong>{diligence.businessInfo.changeCount}</strong></span> : null}
                              {diligence.businessInfo.dishonestCount ? <span style={{ color: "var(--danger)" }}>失信: <strong>{diligence.businessInfo.dishonestCount}</strong></span> : null}
                              {diligence.businessInfo.enforcedCount ? <span style={{ color: "var(--danger)" }}>被执行: <strong>{diligence.businessInfo.enforcedCount}</strong></span> : null}
                              {diligence.businessInfo.pledgeCount ? <span>股权出质: <strong>{diligence.businessInfo.pledgeCount}</strong></span> : null}
                              {diligence.businessInfo.movablePledgeCount ? <span>动产抵押: <strong>{diligence.businessInfo.movablePledgeCount}</strong></span> : null}
                            </div>
                            {diligence.businessInfo.address && <p style={{ fontSize: 11, marginTop: 3, color: "var(--text-muted)" }}>📍 {diligence.businessInfo.address}</p>}
                            {(diligence.businessInfo.contactPhone || diligence.businessInfo.contactEmail || diligence.businessInfo.websites?.length) && (
                              <p style={{ fontSize: 11, marginTop: 2, color: "var(--text-muted)" }}>
                                联系: {[diligence.businessInfo.contactPhone, diligence.businessInfo.contactEmail, ...(diligence.businessInfo.websites || [])].filter(Boolean).join(" · ")}
                              </p>
                            )}
                            {diligence.businessInfo.businessScope && <p style={{ fontSize: 11, marginTop: 2, color: "var(--text-muted)" }}>经营范围: {diligence.businessInfo.businessScope.length > 150 ? diligence.businessInfo.businessScope.slice(0, 150) + "..." : diligence.businessInfo.businessScope}</p>}
                            {diligence.businessInfo.originalNames?.length ? (
                              <p style={{ fontSize: 11, marginTop: 3 }}>曾用名: {diligence.businessInfo.originalNames.slice(0, 3).join("、")}</p>
                            ) : null}
                            {diligence.businessInfo.taxCreditLevels?.length ? (
                              <p style={{ fontSize: 11, marginTop: 2 }}>纳税信用: {diligence.businessInfo.taxCreditLevels.slice(0, 3).join("、")}</p>
                            ) : null}
                            {diligence.businessInfo.shareholders?.length > 0 && (
                              <p style={{ fontSize: 11, marginTop: 3 }}>股东: {diligence.businessInfo.shareholders.slice(0, 5).join("、")}</p>
                            )}
                            {diligence.businessInfo.executives?.length > 0 && (
                              <p style={{ fontSize: 11, marginTop: 2 }}>高管: {diligence.businessInfo.executives.slice(0, 5).join("、")}</p>
                            )}
                            {diligence.businessInfo.abnormalInfo?.length > 0 && (
                              <div style={{ marginTop: 4 }}>
                                <span style={{ fontSize: 11, fontWeight: 600, color: "#e94560" }}>⚠ 经营异常:</span>
                                {diligence.businessInfo.abnormalInfo.slice(0, 3).map((a: string, i: number) => <p key={i} style={{ fontSize: 11, marginLeft: 8, color: "#e94560" }}>• {a}</p>)}
                              </div>
                            )}
                            {diligence.businessInfo.penalties?.length > 0 && (
                              <div style={{ marginTop: 4 }}>
                                <span style={{ fontSize: 11, fontWeight: 600, color: "#e94560" }}>⚠ 行政处罚:</span>
                                {diligence.businessInfo.penalties.slice(0, 3).map((p: string, i: number) => <p key={i} style={{ fontSize: 11, marginLeft: 8, color: "#e94560" }}>• {p}</p>)}
                              </div>
                            )}
                            {diligence.businessInfo.dishonestItems?.length ? (
                              <div style={{ marginTop: 4 }}>
                                <span style={{ fontSize: 11, fontWeight: 600, color: "#e94560" }}>⚠ 失信记录:</span>
                                {diligence.businessInfo.dishonestItems.slice(0, 3).map((p: string, i: number) => <p key={i} style={{ fontSize: 11, marginLeft: 8, color: "#e94560" }}>• {p}</p>)}
                              </div>
                            ) : null}
                            {diligence.businessInfo.enforcedItems?.length ? (
                              <div style={{ marginTop: 4 }}>
                                <span style={{ fontSize: 11, fontWeight: 600, color: "#e94560" }}>⚠ 被执行记录:</span>
                                {diligence.businessInfo.enforcedItems.slice(0, 3).map((p: string, i: number) => <p key={i} style={{ fontSize: 11, marginLeft: 8, color: "#e94560" }}>• {p}</p>)}
                              </div>
                            ) : null}
                            {diligence.businessInfo.permissions?.length ? (
                              <p style={{ fontSize: 11, marginTop: 3 }}>行政许可: {diligence.businessInfo.permissions.slice(0, 3).join("、")}</p>
                            ) : null}
                            {diligence.businessInfo.spotChecks?.length ? (
                              <p style={{ fontSize: 11, marginTop: 2 }}>抽查检查: {diligence.businessInfo.spotChecks.slice(0, 3).join("、")}</p>
                            ) : null}
                            {diligence.businessInfo.apiEntries?.length ? (
                              <details style={{ marginTop: 8 }}>
                                <summary style={{ fontSize: 11, cursor: "pointer", color: "var(--accent-strong)", fontWeight: 600 }}>
                                  工商 API 全量词条 ({diligence.businessInfo.apiEntries.length})
                                </summary>
                                <div style={{ marginTop: 6, maxHeight: 260, overflow: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
                                  {diligence.businessInfo.apiEntries.map((entry, i) => (
                                    <div key={`${entry.path}-${i}`} style={{
                                      display: "grid",
                                      gridTemplateColumns: "minmax(160px, 0.8fr) minmax(180px, 1.2fr)",
                                      gap: 8,
                                      padding: "5px 8px",
                                      borderBottom: i === diligence.businessInfo!.apiEntries!.length - 1 ? "none" : "1px solid var(--border)",
                                      fontSize: 11,
                                      lineHeight: 1.45,
                                    }}>
                                      <code style={{ color: "var(--text-muted)", whiteSpace: "normal", wordBreak: "break-all" }}>{entry.path}</code>
                                      <span style={{ color: "var(--text-strong)", wordBreak: "break-word" }}>{entry.value}</span>
                                    </div>
                                  ))}
                                </div>
                              </details>
                            ) : null}
                          </div>
                        )}
                        {diligence.businessInfo?.error && (
                          <div style={{ marginBottom: 10, fontSize: 12, color: "var(--text-muted)" }}>
                            <span className="detail-label">🏛️ 工商信息</span>
                            <p style={{ marginTop: 3 }}>⚠ {diligence.businessInfo.error}</p>
                          </div>
                        )}
                        {diligence.sentiment && (
                          <div style={{ marginBottom: 10 }}>
                            <span className="detail-label">舆情分析</span>
                            {diligence.sentiment.positive?.length > 0 && (
                              <div className="job-tags" style={{ marginTop: 3, gap: 4 }}>
                                {diligence.sentiment.positive.map((s: string, i: number) => <span key={i} className="tag tag--green" style={{ fontSize: 10 }}>{s}</span>)}
                              </div>
                            )}
                            {diligence.sentiment.negative?.length > 0 && (
                              <div className="job-tags" style={{ marginTop: 3, gap: 4 }}>
                                {diligence.sentiment.negative.map((s: string, i: number) => <span key={i} className="tag tag--red" style={{ fontSize: 10 }}>{s}</span>)}
                              </div>
                            )}
                            {diligence.sentiment.evidenceLinks?.length > 0 && (
                              <div style={{ marginTop: 4 }}>
                                {diligence.sentiment.evidenceLinks.map((l: string, i: number) => (
                                  <a key={i} href={l} target="_blank" rel="noopener"
                                    style={{ fontSize: 11, display: "block", color: "var(--accent)" }}>🔗 {l}</a>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
	                        {diligence.industryOutlook && (
	                          <div style={{ marginBottom: 10 }}>
	                            <span className="detail-label">行业前景</span>
	                            <div style={{ fontSize: 12, marginTop: 3 }}>
	                              <p style={{ margin: "2px 0" }}>
	                                行业: {diligence.industryOutlook.industry || diligence.businessInfo?.registeredIndustry || diligence.businessInfo?.industry || "—"}
	                              </p>
	                              <p style={{ margin: "2px 0" }}>趋势: {diligence.industryOutlook.trend || "—"} · 政策: {diligence.industryOutlook.policy || "—"} · 市场: {diligence.industryOutlook.marketSpace || "—"}</p>
	                              {diligence.industryOutlook.advantages?.length ? (
	                                <div className="job-tags" style={{ marginTop: 3, gap: 4 }}>
	                                  {diligence.industryOutlook.advantages.slice(0, 4).map((r: string, i: number) => <span key={i} className="tag tag--green" style={{ fontSize: 10 }}>{r}</span>)}
	                                </div>
	                              ) : null}
	                              {diligence.industryOutlook.disadvantages?.length ? (
	                                <div className="job-tags" style={{ marginTop: 3, gap: 4 }}>
	                                  {diligence.industryOutlook.disadvantages.slice(0, 4).map((r: string, i: number) => <span key={i} className="tag tag--muted" style={{ fontSize: 10 }}>{r}</span>)}
	                                </div>
	                              ) : null}
	                              {diligence.industryOutlook.risks?.length > 0 && (
	                                <div className="job-tags" style={{ marginTop: 3, gap: 4 }}>
	                                  {diligence.industryOutlook.risks.map((r: string, i: number) => <span key={i} className="tag tag--red" style={{ fontSize: 10 }}>{r}</span>)}
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                        {diligence.recruitment && (
                          <div style={{ marginBottom: 8 }}>
                            <span className="detail-label">招聘分析</span>
                            <p style={{ fontSize: 12, marginTop: 2 }}>
                              活跃: {diligence.recruitment.activePositions || "—"} · 薪资: {diligence.recruitment.salaryCompetitiveness || "—"} · JD: {diligence.recruitment.jdQuality || "—"}
                            </p>
                          </div>
                        )}
                        <div style={{ marginTop: 10 }}>
                          <span className="detail-label">人工备注</span>
                          <textarea className="form-input" rows={2}
                            value={diligence.userNotes || ""}
                            onChange={async (e) => {
                              const note = e.target.value;
                              const next = { ...diligence, userNotes: note };
                              dispatch(actions.setDiligenceReports({ ...diligenceRef.current, [job.company]: next }));
                              try { await saveDiligenceNote(diligence.companyKey || diligence.companyName || job.company, note); }
                              catch (err) { setError(err instanceof Error ? err.message : "备注保存失败"); }
                            }}
                            placeholder="记录面试关注点、风险判断或后续动作"
                            style={{ width: "100%", marginTop: 6, fontSize: 12 }} />
                        </div>
                        <div style={{ marginTop: 10 }}>
                          <button type="button" className="button-quiet" onClick={() => toggleCard(job.id, "chatExpanded")}
                            style={{ fontSize: 12 }}>
                            {cs.chatExpanded ? "收起对话" : "💬 与 AI 讨论尽调结果"}
                          </button>
                          {cs.chatExpanded && (
                            <div style={{ marginTop: 8 }}>
                              <ChatPanel chatKey={`dil-dd-${job.company}`} step="analyze" context={{ company: job.company, diligence }} title="尽调对话"
                                placeholder="讨论尽调结果…"
                                onApply={async (messages) => {
                                  try {
                                    const report = await evaluateCompany({
                                      company_name: job.company, job_title: job.title,
                                      jd_text: job.jd_text, jd_analysis: jdAnalysesRef.current[job.id] || null,
                                      chat_history: messages,
                                    });
                                    dispatch(actions.setDiligenceReports(withDiligenceReport(job, report)));
                                  } catch { setError("应用尽调结果失败"); }
                                }} />
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </section>
  );
}
