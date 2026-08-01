import { useState, useEffect, useMemo } from "react";
import { useWorkflowState, useWorkflowDispatch, actions } from "../lib/store";
import { exportRankingsUrl, getRankingResults, getRankingWeights, getRankingWeightTemplates, getWorkflowCenter, listJobPool, rankJobs, saveRankingWeights } from "../lib/api";
import { filterRankingsByMinimumScore, filterRankingsBySelectedJobs, findFallbackRankingsBySelectedJobs, findUnrankedSelectedJobs, isFallbackRanking, resolveGreetingSelectionFromRankings } from "../lib/rankings";
import { EmptyState, ErrorBanner } from "../components/SharedUI";
import type { JobPosting, RankingResult, RankingWeightTemplate, RankingWeights, WorkflowRuntimeTask } from "../lib/types";
import AiFeedbackButtons from "../components/AiFeedbackButtons";

export default function RankedJobsPage({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const { selectedJobIds, diligenceReports, resumeProfile, rankingResults } = useWorkflowState();
  const dispatch = useWorkflowDispatch();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rankingStatus, setRankingStatus] = useState("");
  const [rankingFailed, setRankingFailed] = useState(false);
  const [failedRankingTask, setFailedRankingTask] = useState<WorkflowRuntimeTask | null>(null);
  const [localSelection, setLocalSelection] = useState<string[]>([]);
  const [minimumScore, setMinimumScore] = useState(70);
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [weights, setWeights] = useState<RankingWeights>({ company_weight: 0.4, match_weight: 0.6 });
  const [templates, setTemplates] = useState<Record<string, RankingWeightTemplate>>({});
  const diligenceDone = Object.keys(diligenceReports).length > 0;
  const visibleRankingResults = useMemo(
    () => filterRankingsBySelectedJobs(rankingResults, selectedJobIds),
    [rankingResults, selectedJobIds],
  );
  const unrankedSelectedJobs = useMemo(
    () => findUnrankedSelectedJobs(jobs, selectedJobIds, rankingResults),
    [jobs, selectedJobIds, rankingResults],
  );
  const fallbackRankingResults = useMemo(
    () => findFallbackRankingsBySelectedJobs(rankingResults, selectedJobIds),
    [rankingResults, selectedJobIds],
  );
  const actionableRankingResults = useMemo(
    () => visibleRankingResults.filter(result => !isFallbackRanking(result)),
    [visibleRankingResults],
  );
  const scoreFilteredRankingResults = useMemo(
    () => filterRankingsByMinimumScore(actionableRankingResults, minimumScore),
    [actionableRankingResults, minimumScore],
  );
  const greetingReadySelection = useMemo(
    () => resolveGreetingSelectionFromRankings(localSelection, visibleRankingResults),
    [localSelection, visibleRankingResults],
  );

  useEffect(() => { setLocalSelection([...selectedJobIds]); }, [selectedJobIds]);

  useEffect(() => {
    getRankingResults()
      .then(r => {
        if (r.rankings?.length) dispatch(actions.setRankingResults(r.rankings));
      })
      .catch(() => {});
    getRankingWeights()
      .then(r => setWeights(r.weights))
      .catch(() => {});
    getRankingWeightTemplates()
      .then(r => setTemplates(r.templates || {}))
      .catch(() => {});
    listJobPool()
      .then(r => setJobs(r.jobs || []))
      .catch(() => {});
    getWorkflowCenter()
      .then(center => setFailedRankingTask(center.recovery.find(task => task.type === "ranking") || null))
      .catch(() => {});
  }, [dispatch]);

  async function onStartRanking() {
    const ids = localSelection.length > 0 ? localSelection : selectedJobIds;
    dispatch(actions.setSelection(ids));
    await runRanking(ids);
  }

  async function onContinueRanking() {
    await runRanking(unrankedSelectedJobs.map(job => job.id), true);
  }

  async function onRefreshFallbackRankings() {
    await runRanking(fallbackRankingResults.map(result => result.jobId), true, true);
  }

  async function runRanking(ids: string[], continueExisting = false, isAiRefresh = false) {
    if (ids.length === 0) {
      setError(continueExisting ? "没有需要继续排序的岗位" : "请先选择需要排序的岗位");
      return;
    }
    setLoading(true); setError(""); setRankingStatus("");
    setRankingFailed(false);
    try {
      const data = await rankJobs(ids, resumeProfile, diligenceReports, weights, continueExisting, isAiRefresh);
      if (data.error) { setError(data.error); setRankingFailed(true); return; }
      dispatch(actions.setRankingResults(data.rankings || []));
      setFailedRankingTask(null);
      const failedRankings = Array.isArray(data.failedRankings) ? data.failedRankings : [];
      if (failedRankings.length > 0) {
        const reasons: Record<string, string> = {
          invalid_response: "返回内容无法解析",
          invalid_schema: "返回字段不完整",
          request_error: "请求异常",
          ai_unavailable: "AI 服务未配置",
        };
        const summary = [...new Set(failedRankings.map((item: { reason?: string }) => reasons[item.reason || ""] || "未知原因"))].join("、");
        setError(`AI 匹配度未完成：${failedRankings.length} 个岗位在自动重试 3 次后仍失败（${summary}）。失败岗位未写入正式排序，可点击“继续排序”仅重试它们。`);
        setRankingFailed(true);
        return;
      }
      if (isAiRefresh) {
        const remaining = (data.rankings || []).filter((result: RankingResult) => ids.includes(result.jobId) && isFallbackRanking(result));
        if (remaining.length > 0) {
          setError(`有 ${remaining.length} 个遗留临时结果未被替换。请点击“继续排序”仅重试这些岗位。`);
          setRankingFailed(true);
          return;
        }
        setRankingStatus(`AI 匹配度已更新 ${ids.length} 个岗位`);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "排序失败"); setRankingFailed(true); }
    finally { setLoading(false); }
  }

  function toggleLocal(id: string) {
    const result = visibleRankingResults.find(item => item.jobId === id);
    if (result && isFallbackRanking(result)) return;
    setLocalSelection(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }

  async function passToGreeting() {
    const greetingJobIds = resolveGreetingSelectionFromRankings(localSelection, visibleRankingResults);
    if (greetingJobIds.length === 0) {
      setError("请先在排序结果中选择要进入打招呼的岗位");
      return;
    }
    console.info("[greeting-selection] 排序页带入打招呼目标", { count: greetingJobIds.length, jobIds: greetingJobIds });
    try {
      const response = await fetch("/api/workflow/greeting-selection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ greetingJobIds }),
      });
      if (!response.ok) throw new Error("保存打招呼目标失败");
      const saved = await response.json() as { greetingJobIds?: unknown };
      const savedIds = Array.isArray(saved.greetingJobIds) ? saved.greetingJobIds.map(String) : greetingJobIds;
      dispatch(actions.setGreetingSelection(savedIds));
      onNavigate?.("greeting");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存打招呼目标失败，请稍后重试");
    }
  }

  function selectByMinimumScore() {
    setLocalSelection(scoreFilteredRankingResults.map(result => result.jobId));
  }

  async function updateCompanyWeight(value: number) {
    const next = { company_weight: value, match_weight: Number((1 - value).toFixed(2)) };
    setWeights(next);
    try {
      const saved = await saveRankingWeights(next);
      setWeights(saved.weights);
    } catch (e) {
      setError(e instanceof Error ? e.message : "权重保存失败");
    }
  }

  async function applyTemplate(template: RankingWeightTemplate) {
    setWeights(template.weights);
    try {
      const saved = await saveRankingWeights(template.weights);
      setWeights(saved.weights);
    } catch (e) {
      setError(e instanceof Error ? e.message : "模板应用失败");
    }
  }

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack"><p className="page-kicker">第四步</p><h2 className="page-title">综合排序</h2><p className="page-copy">公司尽调得分 + AI 简历匹配度分析，综合排序并给出推荐理由。勾选后进入打招呼。</p></div>
        <div style={{ display: "flex", gap: 8 }}>
          {visibleRankingResults.length > 0 && <span className="tag tag--active">已排序 {visibleRankingResults.length} 个</span>}
          {unrankedSelectedJobs.length > 0 && <span className="tag tag--muted">待排序 {unrankedSelectedJobs.length} 个</span>}
          {greetingReadySelection.length > 0 && <span className="tag">{greetingReadySelection.length} 个可打招呼</span>}
          {fallbackRankingResults.length > 0 && <span className="tag tag--red">临时匹配分 {fallbackRankingResults.length} 个</span>}
          {visibleRankingResults.length > 0 && <button type="button" className="button-primary" disabled={greetingReadySelection.length === 0} onClick={passToGreeting}>进入打招呼 ({greetingReadySelection.length}) →</button>}
        </div>
      </div>
      <div className="module-export-bar" aria-label="排序数据导出">
        <span>排序结果</span>
        <a className="button-secondary button-secondary--sm" href={exportRankingsUrl("json")} download>导出 JSON</a>
        <a className="button-secondary button-secondary--sm" href={exportRankingsUrl("csv")} download>导出 CSV</a>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}
      {rankingStatus && <p className="text-success" role="status">{rankingStatus}</p>}

      {!resumeProfile && <div className="panel panel-strong"><div className="panel-inner"><EmptyState icon="📄" title="尚未上传简历" desc="请先在「简历」页面上传并解析简历。" /></div></div>}
      {resumeProfile && !diligenceDone && <div className="panel panel-strong"><div className="panel-inner"><EmptyState icon="🏢" title="尚未完成公司尽调" desc="请先在「尽调」页面对公司进行分析。" /></div></div>}

      {resumeProfile && diligenceDone && (
        <div className="panel panel-strong">
          <div className="panel-inner">
            <div className="page-section__top">
              <div>
                <div className="page-kicker">{visibleRankingResults.length > 0 ? "排序结果" : "开始排序"}</div>
                <div className="toolbar-strip" style={{ marginTop: 8 }}>
                  <span className="text-muted" style={{ fontSize: 12 }}>公司风险 {Math.round(weights.company_weight * 100)}%</span>
                  <input
                    aria-label="公司风险权重"
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={weights.company_weight}
                    onChange={e => updateCompanyWeight(Number(e.target.value))}
                    style={{ width: 180 }}
                  />
                  <span className="text-muted" style={{ fontSize: 12 }}>简历匹配 {Math.round(weights.match_weight * 100)}%</span>
                </div>
                {Object.keys(templates).length > 0 && (
                  <div className="template-chip-row">
                    {Object.entries(templates).map(([key, template]) => (
                      <button key={key} type="button" className="template-chip" onClick={() => applyTemplate(template)} title={template.description}>
                        {template.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                {unrankedSelectedJobs.length > 0 && <button type="button" className="button-secondary" disabled={loading} onClick={onContinueRanking}>继续排序 ({unrankedSelectedJobs.length})</button>}
                {fallbackRankingResults.length > 0 && <button type="button" className="button-secondary" disabled={loading} onClick={onRefreshFallbackRankings}>重新分析 AI 匹配度 ({fallbackRankingResults.length})</button>}
                <button type="button" className="button-primary" disabled={loading} onClick={onStartRanking}>{loading ? "AI 分析中…" : visibleRankingResults.length > 0 ? "重新排序" : "开始综合排序"}</button>
              </div>
            </div>
            {unrankedSelectedJobs.length > 0 && (
              <div className="workflow-recovery-item workflow-todo-item" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.5fr) auto", marginTop: 12 }}>
                <span>有 {unrankedSelectedJobs.length} 个已选岗位还没有排序结果</span>
                <small>{unrankedSelectedJobs.map(job => `${job.company} · ${job.title}`).join("；")}</small>
                <button type="button" className="button-secondary button-secondary--sm" disabled={loading} onClick={onContinueRanking}>继续排序</button>
              </div>
            )}
            {fallbackRankingResults.length > 0 && (
              <div className="workflow-recovery-item workflow-todo-item" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.5fr) auto", marginTop: 12 }}>
                <span>有 {fallbackRankingResults.length} 个岗位曾在 AI 未配置时使用了临时匹配分</span>
                <small>临时匹配分不会进入打招呼；重新分析后才会纳入候选。</small>
                <button type="button" className="button-primary button-secondary--sm" disabled={loading} onClick={onRefreshFallbackRankings}>重新分析 AI 匹配度</button>
              </div>
            )}
            {(rankingFailed || failedRankingTask) && unrankedSelectedJobs.length > 0 && (
              <div className="workflow-recovery-item workflow-todo-item" style={{ gridTemplateColumns: "minmax(0, 1fr) auto", marginTop: 12 }}>
                <span>上一轮排序未完成，AI 配置或网络恢复后可重新排序未完成岗位。{failedRankingTask?.message ? ` 原因：${failedRankingTask.message}` : ""}</span>
                <button type="button" className="button-primary button-secondary--sm" disabled={loading} onClick={onContinueRanking}>重新排序未完成岗位 ({unrankedSelectedJobs.length})</button>
              </div>
            )}
            {visibleRankingResults.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="panel panel-muted ranking-score-filter" aria-label="推荐得分筛选">
                  <div className="panel-inner">
                    <div className="toolbar-strip">
                      <strong>推荐得分筛选</strong>
                      {[80, 70, 60].map(score => (
                        <button key={score} type="button" className="button-secondary button-secondary--sm" onClick={() => setMinimumScore(score)}>≥ {score}</button>
                      ))}
                      <label className="text-muted" style={{ fontSize: 12 }}>
                        最低分
                        <input className="form-input form-input--inline" type="number" min="0" max="100" value={minimumScore}
                          onChange={event => setMinimumScore(Math.max(0, Math.min(100, Number(event.target.value) || 0)))} style={{ width: 70, marginLeft: 6 }} />
                      </label>
                      <span className="text-muted" style={{ fontSize: 12 }}>符合条件 {scoreFilteredRankingResults.length} 个</span>
                      <button type="button" className="button-primary button-secondary--sm" disabled={scoreFilteredRankingResults.length === 0} onClick={selectByMinimumScore}>一键选择符合项</button>
                    </div>
                  </div>
                </div>
                {visibleRankingResults.map((r, i) => {
                  const temporary = isFallbackRanking(r);
                  const sel = !temporary && localSelection.includes(r.jobId);
                  return (
                    <div key={r.jobId} className="panel panel-muted" style={{ marginBottom: 12, borderLeft: sel ? "4px solid #3b82f6" : "4px solid transparent" }}>
                      <div className="panel-inner">
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
                            <input type="checkbox" checked={sel} disabled={temporary} aria-label={temporary ? "临时匹配分不可进入打招呼" : "加入打招呼候选"} onChange={() => toggleLocal(r.jobId)} style={{ width: 16, height: 16, accentColor: "#3b82f6" }} />
                            <span style={{ fontSize: 20, fontWeight: 700, color: "#3b82f6" }}>#{i + 1}</span>
                            <div><strong style={{ fontSize: 15 }}>{r.jobTitle}</strong><p className="text-muted" style={{ fontSize: 13 }}>{r.company} · {r.salary}</p></div>
                          </div>
                          <div style={{ textAlign: "right" }}><div style={{ fontSize: 28, fontWeight: 700, color: r.compositeScore >= 70 ? "#16a34a" : r.compositeScore >= 50 ? "#d97706" : "#e94560" }}>{r.compositeScore}</div><span className="text-muted" style={{ fontSize: 11 }}>综合分</span></div>
                        </div>
	                        <div className="job-tags" style={{ marginTop: 8, marginLeft: 36 }}>
	                          <span className="tag">公司: {r.companyScore}</span><span className="tag tag--green">匹配: {r.matchScore}</span>
	                          {r.weights && <span className="tag tag--muted">权重 {Math.round(r.weights.company_weight * 100)}/{Math.round(r.weights.match_weight * 100)}</span>}
	                          {r.weights?.feedbackAdjusted && <span className="tag tag--green">已结合反馈</span>}
	                          {temporary && <span className="tag tag--red">临时匹配分 · 不进入打招呼</span>}
	                          <span className={`tag ${r.recommendation === "strong" ? "tag--green" : r.recommendation === "recommend" ? "tag" : r.recommendation === "consider" ? "tag--muted" : "tag--red"}`}>{r.recommendation === "strong" ? "强烈推荐" : r.recommendation === "recommend" ? "推荐" : r.recommendation === "consider" ? "可考虑" : "不推荐"}</span>
	                        </div>
	                        {r.reason && <p style={{ fontSize: 13, marginTop: 8, marginLeft: 36 }}>{r.reason}</p>}
                          <div style={{ marginLeft: 36, marginTop: 8 }}>
                            <AiFeedbackButtons
                              domain="ranking"
                              targetId={r.jobId}
                              compact
                              context={{
                                company: r.company,
                                score: r.compositeScore,
                                companyScore: r.companyScore,
                                matchScore: r.matchScore,
                                recommendation: r.recommendation,
                              }}
                            />
                          </div>
                          {r.explanation?.nextStep && (
                            <div className="ranking-explanation" style={{ marginLeft: 36 }}>
                              <strong>{r.explanation.nextStep}</strong>
                              <p>{r.explanation.companyReason}</p>
                              {r.explanation.riskSignals?.length > 0 && (
                                <div className="job-tags">
                                  {r.explanation.riskSignals.slice(0, 3).map((item, idx) => <span key={idx} className="tag tag--red">{item}</span>)}
                                </div>
                              )}
                              {r.explanation.preferenceSignals?.length ? (
                                <div className="job-tags">
                                  {r.explanation.preferenceSignals.slice(0, 3).map((item, idx) => <span key={idx} className="tag tag--green">{item}</span>)}
                                </div>
                              ) : null}
                            </div>
                          )}
	                        {(r.matchHighlights?.length > 0 || r.matchGaps?.length > 0) && (
	                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10, marginTop: 10, marginLeft: 36 }}>
	                            {r.matchHighlights?.length > 0 && (
	                              <div>
	                                <span className="detail-label">匹配亮点</span>
	                                <div className="job-tags" style={{ marginTop: 5 }}>
	                                  {r.matchHighlights.slice(0, 5).map((item, idx) => <span key={idx} className="tag tag--green">{item}</span>)}
	                                </div>
	                              </div>
	                            )}
	                            {r.matchGaps?.length > 0 && (
	                              <div>
	                                <span className="detail-label">主要短板</span>
	                                <div className="job-tags" style={{ marginTop: 5 }}>
	                                  {r.matchGaps.slice(0, 5).map((item, idx) => <span key={idx} className="tag tag--red">{item}</span>)}
	                                </div>
	                              </div>
	                            )}
	                          </div>
	                        )}
	                      </div>
	                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
