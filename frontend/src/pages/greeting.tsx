import { useState, useEffect } from "react";
import {
  listJobPool as poolJobs,
  analyzeJD,
  aiOptimizeResume,
  exportResumePdf,
	  tagJob,
	  confirmSendRecord,
	  updateSendRecord,
  getGreetingDrafts,
  getSendRecords,
  saveGreetingDrafts,
} from "../lib/api";
import type { JobPosting } from "../lib/types";
import { useWorkflowState, useWorkflowDispatch, actions } from "../lib/store";
import ChatPanel from "../components/ChatPanel";
import { EmptyState, ErrorBanner } from "../components/SharedUI";

export default function GreetingPage() {
  const { selectedJobIds, resumeProfile, jdAnalyses, optimizations, greetingTexts, chatMessages } = useWorkflowState();
  const dispatch = useWorkflowDispatch();

  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [loading, setLoading] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [greetedStatus, setGreetedStatus] = useState<Record<string, boolean>>({});
  const [customTags, setCustomTags] = useState<Record<string, string[]>>({});
  const [tagInputs, setTagInputs] = useState<Record<string, string>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [pdfTemplate, setPdfTemplate] = useState<"modern" | "classic" | "ats">("modern");

  useEffect(() => {
    poolJobs().then(r => {
      const all: JobPosting[] = r.jobs || [];
      setJobs(all.filter(j => selectedJobIds.includes(j.id)));
      const g: Record<string, boolean> = {};
      const t: Record<string, string[]> = {};
      all.forEach((j) => { if (j.greeted) g[j.id] = true; if (j.tags?.length) t[j.id] = j.tags; });
      setGreetedStatus(g);
      setCustomTags(t);
    }).catch((err) => {
      console.warn("[greeting] 加载岗位失败:", err);
    });
  }, [selectedJobIds]);

  useEffect(() => {
    getGreetingDrafts()
      .then(r => {
        if (r.greetings && Object.keys(r.greetings).length > 0) {
          dispatch(actions.setGreetingTexts({ ...greetingTexts, ...r.greetings }));
        }
      })
      .catch(() => {});
    getSendRecords()
      .then(r => {
        const next: Record<string, boolean> = {};
        r.records?.forEach(record => {
          if (record.status === "sent") next[record.jobId] = true;
        });
        if (Object.keys(next).length > 0) setGreetedStatus(prev => ({ ...prev, ...next }));
      })
      .catch(() => {});
  }, [dispatch]);

  // 确保 JD 分析存在 — 优先从 store 读取，没有则请求
  async function ensureJDAnalysis(job: JobPosting) {
    if (jdAnalyses[job.id]) return jdAnalyses[job.id];
    setLoading(prev => ({ ...prev, [job.id + "-jd"]: "分析中…" }));
    try {
      const data = await analyzeJD({ title: job.title, company: job.company, jd_text: job.jd_text });
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
      const data = await aiOptimizeResume(resumeProfile, { title: job.title, company: job.company, jd_text: job.jd_text }, null, jdA || undefined);
      dispatch(actions.setOptimizations({ ...optimizations, [job.id]: data }));
    } catch (err) { setError(err instanceof Error ? err.message : "优化失败"); }
    finally { setLoading(prev => ({ ...prev, [job.id + "-opt"]: "" })); }
  }

	  async function onGenerateGreeting(job: JobPosting) {
	    setLoading(prev => ({ ...prev, [job.id + "-greet"]: "生成中…" }));
	    try {
	      const jdA = await ensureJDAnalysis(job);
	      const skills = resumeProfile?.skills?.join("、") || "相关技术";
	      const highlights = jdA?.must_have_skills?.slice(0, 3).join("、") || job.keywords?.slice(0, 3).join("、") || "岗位要求";
	      const next = { ...greetingTexts, [job.id]: `您好，我对贵司的「${job.title}」岗位非常感兴趣。我有 ${skills} 方面的经验，熟悉 ${highlights} 等技术，希望能有机会进一步沟通。` };
	      dispatch(actions.setGreetingTexts(next));
	      await saveGreetingDrafts(next);
	    } catch (err) { setError(err instanceof Error ? err.message : "生成失败"); }
	    finally { setLoading(prev => ({ ...prev, [job.id + "-greet"]: "" })); }
	  }

	  async function markGreeted(jobId: string) {
	    const oldVal = !!greetedStatus[jobId];
	    const newVal = !oldVal;
	    setGreetedStatus(prev => ({ ...prev, [jobId]: newVal }));
	    try {
	      await tagJob(jobId, { greeted: newVal });
	      if (newVal) await confirmSendRecord(jobId);
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

  async function onExportPdf(job: JobPosting) {
    const opt = optimizations[job.id]; if (!opt || !resumeProfile) return;
    setLoading(prev => ({ ...prev, [job.id + "-pdf"]: "导出中…" }));
    try { await exportResumePdf({ profile: resumeProfile, optimization: opt, company: job.company, job_title: resumeProfile.title || job.title, template: pdfTemplate }); }
    catch (err) { setError(err instanceof Error ? err.message : "导出失败"); }
    finally { setLoading(prev => ({ ...prev, [job.id + "-pdf"]: "" })); }
  }

  const bossUrl = (job: JobPosting) => job.source_url || `https://www.zhipin.com/web/geek/job?query=${encodeURIComponent(job.title)}&city=100010000`;

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">第五步</p>
          <h2 className="page-title">打招呼语与简历修订</h2>
          <p className="page-copy">根据岗位 JD 生成定制打招呼语，AI 逐岗位优化简历并支持导出。</p>
        </div>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {selectedJobIds.length === 0 && (
        <div className="panel panel-strong"><div className="panel-inner"><EmptyState icon="👋" title="尚未选择岗位" desc="请在「排序」页面勾选岗位后进入此页面。" /></div></div>
      )}

      {jobs.map(job => {
	        const opt = optimizations[job.id];
	        const greeting = greetingTexts[job.id];
	        const readyItems = [
	          { label: "话术", ok: !!greeting },
	          { label: "简历", ok: !!opt },
	          { label: "PDF", ok: !!opt },
	          { label: "招呼", ok: !!greetedStatus[job.id] },
	        ];
	        return (
	          <div key={job.id} className="panel panel-strong">
	            <div className="panel-inner">
              {/* 岗位信息头 */}
              <div className="page-section__top">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <strong style={{ fontSize: 15 }}>{job.title}</strong>
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
                  {(customTags[job.id] || []).map(t => <span key={t} className="tag">{t}</span>)}
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
	              </div>

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
                </div>
                {greeting ? (
                  <textarea className="form-input" value={greeting}
	                    onChange={e => {
	                      const next = { ...greetingTexts, [job.id]: e.target.value };
	                      dispatch(actions.setGreetingTexts(next));
	                      saveGreetingDrafts(next).catch((err) => {
	                        setError(err instanceof Error ? err.message : "话术保存失败");
	                      });
	                    }}
                    rows={3} style={{ width: "100%", fontSize: 13 }} />
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
                    <button type="button" className="button-secondary"
                      disabled={!!loading[job.id + "-pdf"]}
                      onClick={() => onExportPdf(job)} style={{ fontSize: 12 }}>
                      {loading[job.id + "-pdf"] || "📄 下载PDF"}
                    </button>
                    </>
                  )}
                </div>
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
                        const data = await aiOptimizeResume(resumeProfile, { title: job.title, company: job.company, jd_text: job.jd_text }, null, jdA || undefined, messages);
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
