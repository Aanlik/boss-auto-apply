import { useState, useEffect, useMemo } from "react";
import { useWorkflowState, useWorkflowDispatch, actions } from "../lib/store";
import { exportRankingsUrl, getRankingResults, getRankingWeights, getRankingWeightTemplates, rankJobs, saveRankingWeights } from "../lib/api";
import { filterRankingsBySelectedJobs } from "../lib/rankings";
import { EmptyState, ErrorBanner } from "../components/SharedUI";
import type { RankingWeightTemplate, RankingWeights } from "../lib/types";
import AiFeedbackButtons from "../components/AiFeedbackButtons";

export default function RankedJobsPage({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const { selectedJobIds, diligenceReports, resumeProfile, rankingResults } = useWorkflowState();
  const dispatch = useWorkflowDispatch();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [localSelection, setLocalSelection] = useState<string[]>([]);
  const [weights, setWeights] = useState<RankingWeights>({ company_weight: 0.4, match_weight: 0.6 });
  const [templates, setTemplates] = useState<Record<string, RankingWeightTemplate>>({});
  const diligenceDone = Object.keys(diligenceReports).length > 0;
  const visibleRankingResults = useMemo(
    () => filterRankingsBySelectedJobs(rankingResults, selectedJobIds),
    [rankingResults, selectedJobIds],
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
  }, [dispatch]);

  async function onStartRanking() {
    setLoading(true); setError("");
    try {
      const ids = localSelection.length > 0 ? localSelection : selectedJobIds;
      const data = await rankJobs(ids, resumeProfile, diligenceReports, weights);
      if (data.error) { setError(data.error); return; }
      dispatch(actions.setRankingResults(data.rankings || []));
    } catch (e) { setError(e instanceof Error ? e.message : "排序失败"); }
    finally { setLoading(false); }
  }

  function toggleLocal(id: string) {
    setLocalSelection(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }

  function passToGreeting() {
    dispatch(actions.setSelection(localSelection.length > 0 ? localSelection : visibleRankingResults.map(r => r.jobId)));
    onNavigate?.("greeting");
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
          {localSelection.length > 0 && <span className="tag">{localSelection.length} 个已选</span>}
          {(visibleRankingResults.length > 0 || localSelection.length > 0) && <button type="button" className="button-primary" onClick={passToGreeting}>进入打招呼 →</button>}
        </div>
      </div>
      <div className="module-export-bar" aria-label="排序数据导出">
        <span>排序结果</span>
        <a className="button-secondary button-secondary--sm" href={exportRankingsUrl("json")} download>导出 JSON</a>
        <a className="button-secondary button-secondary--sm" href={exportRankingsUrl("csv")} download>导出 CSV</a>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

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
              <button type="button" className="button-primary" disabled={loading} onClick={onStartRanking}>{loading ? "AI 分析中…" : visibleRankingResults.length > 0 ? "重新排序" : "开始综合排序"}</button>
            </div>
            {visibleRankingResults.length > 0 && (
              <div style={{ marginTop: 16 }}>
                {visibleRankingResults.map((r, i) => {
                  const sel = localSelection.includes(r.jobId);
                  return (
                    <div key={r.jobId} className="panel panel-muted" style={{ marginBottom: 12, borderLeft: sel ? "4px solid #3b82f6" : "4px solid transparent" }}>
                      <div className="panel-inner">
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
                            <input type="checkbox" checked={sel} onChange={() => toggleLocal(r.jobId)} style={{ width: 16, height: 16, accentColor: "#3b82f6" }} />
                            <span style={{ fontSize: 20, fontWeight: 700, color: "#3b82f6" }}>#{i + 1}</span>
                            <div><strong style={{ fontSize: 15 }}>{r.jobTitle}</strong><p className="text-muted" style={{ fontSize: 13 }}>{r.company} · {r.salary}</p></div>
                          </div>
                          <div style={{ textAlign: "right" }}><div style={{ fontSize: 28, fontWeight: 700, color: r.compositeScore >= 70 ? "#16a34a" : r.compositeScore >= 50 ? "#d97706" : "#e94560" }}>{r.compositeScore}</div><span className="text-muted" style={{ fontSize: 11 }}>综合分</span></div>
                        </div>
	                        <div className="job-tags" style={{ marginTop: 8, marginLeft: 36 }}>
	                          <span className="tag">公司: {r.companyScore}</span><span className="tag tag--green">匹配: {r.matchScore}</span>
	                          {r.weights && <span className="tag tag--muted">权重 {Math.round(r.weights.company_weight * 100)}/{Math.round(r.weights.match_weight * 100)}</span>}
                            {r.weights?.feedbackAdjusted && <span className="tag tag--green">已结合反馈</span>}
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
