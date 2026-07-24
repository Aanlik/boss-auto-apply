import { useState, useEffect, type ChangeEvent } from "react";
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";
import { parseResumeFile, evaluateResume, analyzeJD, aiOptimizeResume, listUploadedFiles, deleteUploadedFile, updateProfile, loadResume, getActiveResume } from "../lib/api";
import type { UploadedFile } from "../lib/types";
import ChatPanel from "../components/ChatPanel";
import type { JobPosting, ResumeProfile, ResumeEvaluation, JDAnalysis, ResumeOptimizationResult } from "../lib/types";

interface ResumesPageProps {
  selectedJob: JobPosting | null;
}

// 管道步骤
type Step = "parse" | "evaluate" | "analyze" | "optimize" | "preview";

export default function ResumesPage({ selectedJob }: ResumesPageProps) {
  // Step 1: 解析
  const [profile, setProfile] = useState<ResumeProfile | null>(null);
  const [fileName, setFileName] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);

  // Step 2: 评估
  const [evaluation, setEvaluation] = useState<ResumeEvaluation | null>(null);

  // Step 3: JD 分析
  const [jdAnalysis, setJdAnalysis] = useState<JDAnalysis | null>(null);

  // Step 4: 优化
  const [optimization, setOptimization] = useState<ResumeOptimizationResult | null>(null);

  // 状态
  const [activeStep, setActiveStep] = useState<Step>("parse");
  const [loading, setLoading] = useState("");

  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  // ── 复用工具函数 ──
  function resetPipeline() {
    setError("");
    setEvaluation(null);
    setJdAnalysis(null);
    setOptimization(null);
  }
  function restoreResumeData(data: any) {
    setProfile(data.profile);
    setResumeText(data.raw_text || "");
    setFileName(data.file_id || "");
    if (data.eval) setEvaluation(data.eval);
    if (data.jd) setJdAnalysis(data.jd);
    if (data.optimization) setOptimization(data.optimization);
    const hasE = !!(data.eval), hasJ = !!(data.jd);
    if (hasE && hasJ) setActiveStep("optimize");
    else if (hasE) setActiveStep("analyze");
  }
  function catchError(err: unknown, fallback: string) {
    setError(err instanceof Error ? err.message : fallback);
  }

  // 页面加载时恢复上次的简历数据
  useEffect(() => {
    getActiveResume().then(data => {
      if (data.profile) restoreResumeData(data);
    }).catch(() => {});
    listUploadedFiles().then(r => setUploadedFiles(r.files)).catch(() => {});
  }, []);

  // === Step 1: 上传并解析 ===
  async function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setLoading("parse");
    resetPipeline();
    try {
      const data = await parseResumeFile(file);
      setProfile(data.profile);
      setResumeText(data.raw_text);
      setActiveStep("evaluate");
      listUploadedFiles().then(r => setUploadedFiles(r.files)).catch(() => {});
    } catch (err) {
      setProfile(null);
      catchError(err, "简历解析失败");
    } finally {
      setLoading("");
    }
  }

  // === 编辑解析信息 ===
  function updateProfileField(field: string, value: string) {
    if (!profile) return;
    const updated = { ...profile, [field]: value };
    setProfile(updated);
  }

  function updateProfileSkills(value: string) {
    if (!profile) return;
    const updated = { ...profile, skills: value.split(/[,，、]/).map(s => s.trim()).filter(Boolean) };
    setProfile(updated);
  }

  async function onSaveProfile() {
    if (!profile) return;
    try { await updateProfile(profile); setError(""); }
    catch (err) { catchError(err, "保存失败"); }
  }

  // === 附件管理 ===
  async function onLoadResume(fileId: string) {
    setLoading("parse");
    resetPipeline();
    try {
      const data = await loadResume(fileId);
      restoreResumeData(data);
      setActiveStep("parse");
    } catch (err) {
      catchError(err, "加载失败");
    } finally {
      setLoading("");
    }
  }

  async function onDeleteFile(fileId: string) {
    try { await deleteUploadedFile(fileId); setUploadedFiles(prev => prev.filter(f => f.id !== fileId)); }
    catch (err) { catchError(err, "删除失败"); }
  }

  // === Step 2: AI 评估简历 ===
  async function onEvaluate(chatHistory?: Array<{role: string; content: string}>) {
    if (!profile) return;
    setLoading("evaluate");
    setError("");
    try {
      const data = await evaluateResume(profile, resumeText, chatHistory);
      setEvaluation(data);
      setActiveStep("analyze");
    } catch (err) {
      catchError(err, "AI 评估失败");
    } finally {
      setLoading("");
    }
  }

  // === Step 3: AI 分析 JD ===
  async function onAnalyzeJD(chatHistory?: Array<{role: string; content: string}>) {
    if (!selectedJob) return;
    setLoading("analyze");
    setError("");
    try {
      const data = await analyzeJD({
        title: selectedJob.title,
        company: selectedJob.company,
        jd_text: selectedJob.jd_text,
      }, chatHistory);
      setJdAnalysis(data);
      setActiveStep("optimize");
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 分析 JD 失败");
    } finally {
      setLoading("");
    }
  }

  // === Step 4: AI 优化 ===
  async function onOptimize(chatHistory?: Array<{role: string; content: string}>) {
    if (!profile || !selectedJob) return;
    setLoading("optimize");
    setError("");
    try {
      const data = await aiOptimizeResume(profile, selectedJob, evaluation, jdAnalysis, chatHistory);
      setOptimization(data);
    } catch (err) {
      catchError(err, "AI 优化失败");
    } finally {
      setLoading("");
    }
  }

  // === 打印/导出预览版简历 ===
  async function onDownload() {
    if (!profile) { setError("请先上传并解析简历"); return; }
    if (!optimization) { setError("请先完成 AI 优化 (Step 4)"); return; }
    const previewEl = document.getElementById("resume-preview-print");
    if (!previewEl) { setError("预览内容未找到"); return; }
    setDownloading(true);
    setError("");

    try {
      // Step 1: 截图预览区为 Canvas
      const canvas = await html2canvas(previewEl, {
        scale: Math.max(window.devicePixelRatio || 1, 2),
        useCORS: true,
        backgroundColor: "#ffffff",
        logging: false,
        onclone(clonedDoc) {
          const clone = clonedDoc.getElementById("resume-preview-print");
          if (clone) {
            // 去内边距
            const inner = clone.firstElementChild as HTMLElement;
            if (inner) inner.style.padding = "0";
            // 去所有圆角和边框
            clone.querySelectorAll("*").forEach((el: any) => {
              if (el.style.borderRadius) el.style.borderRadius = "0";
              if (el.style.border && el.style.border !== "0px") el.style.border = "none";
            });
          }
        }
      });

      // Step 2: Canvas → PDF (A4)
      const imgData = canvas.toDataURL("image/png");
      // 794px 预览区 → 210mm PDF 宽，严格等比无白边
      const pdfW = 210;
      const pdfH = 297;
      const scale = pdfW / canvas.width;
      const imgH = canvas.height * scale;

      const pdf = new jsPDF({ unit: "mm", format: "a4", compress: true });
      pdf.addImage(imgData, "PNG", 0, 0, pdfW, imgH);

      // 超出单页时追加
      for (let y = pdfH; y < imgH; y += pdfH) {
        pdf.addPage();
        pdf.addImage(imgData, "PNG", 0, -y, pdfW, imgH);
      }

      // Step 3: 触发下载
      const company = selectedJob?.company || "公司";
      const jobTitle = profile.title || selectedJob?.title || "岗位";
      pdf.save(`${company}-${jobTitle}.pdf`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError("导出失败: " + msg);
    } finally {
      setDownloading(false);
    }
  }

  // === 步骤指示器 ===
  const steps: { key: Step; label: string; done: boolean }[] = [
    { key: "parse", label: "上传解析", done: !!profile },
    { key: "evaluate", label: "AI 评估", done: !!evaluation },
    { key: "analyze", label: "JD 分析", done: !!jdAnalysis },
    { key: "optimize", label: "AI 优化", done: !!optimization },
    { key: "preview", label: "生成简历", done: false },
  ];

  const scoreColor = (s: number) => (s >= 70 ? "var(--accent)" : s >= 40 ? "var(--warning)" : "var(--danger)");

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">简历模块</p>
          <h2 className="page-title">AI 驱动：解析 → 评估 → JD 分析 → 优化 → 生成简历</h2>
          <p className="page-copy">上传简历后，AI 解析→评估→分析 JD→针对性优化→生成模板化简历 PDF。</p>
        </div>
        {/* 步骤指示器 */}
        <div className="pipeline-steps">
          {steps.map((s, i) => (
            <div key={s.key} className={`pipeline-step ${activeStep === s.key ? "pipeline-step--active" : ""} ${s.done ? "pipeline-step--done" : ""}`}>
              <span className="pipeline-step__num">{s.done ? "✓" : i + 1}</span>
              <span className="pipeline-step__label">{s.label}</span>
              {i < steps.length - 1 && <span className="pipeline-step__connector" />}
            </div>
          ))}
        </div>
      </div>

      {error ? <div className="banner banner-error">{error}</div> : null}

      <div className="panel panel-strong" style={{overflow:"visible"}}>
        <div className="panel-inner" style={{display:"flex",gap:16,alignItems:"flex-start",overflow:"visible"}}>

          {/* === 左侧主区 === */}
          <div className="workbench-main section-grid" style={{flex:1,minWidth:0,overflow:"visible"}}>

            {/* Step 1: 上传 */}
            <section className="page-section">
              <div className="upload-dropzone">
                <label className="field">
                  <span className="field-label">上传简历（Step 1）</span>
                  <input
                    aria-label="resume-upload"
                    type="file"
                    accept=".txt,.md,.pdf,.doc,.docx"
                    onChange={onFileChange}
                    disabled={loading !== ""}
                  />
                </label>
                <p className="workspace-target-meta">支持 .txt / .md / .pdf / .docx。上传后自动解析。</p>
              </div>
            </section>

            {/* 解析概览 — 可编辑 */}
            {profile && (
              <div className="panel panel-muted">
                <div className="panel-inner section-grid">
                  <div className="page-kicker" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>解析概览</span>
                    <button type="button" className="button-secondary" onClick={onSaveProfile} style={{ fontSize: 11, padding: '3px 10px' }}>保存修改</button>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    <FieldRow label="文件" value={fileName} onChange={v => setFileName(v)} />
                    <FieldRow label="姓名" value={profile.name} onChange={v => updateProfileField('name', v)} />
                    <FieldRow label="岗位" value={profile.title} onChange={v => updateProfileField('title', v)} />
                    <FieldRow label="电话" value={profile.phone || ''} onChange={v => updateProfileField('phone', v)} />
                    <FieldRow label="邮箱" value={profile.email || ''} onChange={v => updateProfileField('email', v)} />
                    <FieldRow label="性别" value={profile.gender || ''} onChange={v => updateProfileField('gender', v)} />
                    <FieldRow label="出生" value={profile.birth || ''} onChange={v => updateProfileField('birth', v)} />
                    <FieldRow label="现居" value={profile.location || ''} onChange={v => updateProfileField('location', v)} />
                  </div>
                  <div className="field" style={{ marginTop: 4 }}>
                    <span className="field-label" style={{ fontSize: 12 }}>技能（逗号分隔）</span>
                    <input
                      className="form-input form-input--inline"
                      value={(profile.skills || []).join('、')}
                      onChange={e => updateProfileSkills(e.target.value)}
                      placeholder="Python、Go、Docker..."
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: 评估按钮 */}
            {profile && !evaluation && (
              <div className="toolbar-row">
                <button type="button" className="button-primary" onClick={() => onEvaluate()} disabled={loading !== ""}>
                  {loading === "evaluate" ? "AI 评估中..." : "Step 2: AI 评估简历"}
                </button>
              </div>
            )}

            {/* 评估结果 */}
            {evaluation && (
              <section className="panel panel-muted">
                <div className="panel-inner section-grid">
                  <div className="page-kicker" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>AI 简历评估</span>
                    <button type="button" className="button-secondary" onClick={() => onEvaluate()} disabled={loading !== ""} style={{ fontSize: 12, padding: '4px 10px' }}>
                      {loading === "evaluate" ? "评估中..." : "🔄 重新评估"}
                    </button>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div className="score-badge" style={{ background: scoreColor(evaluation.overall_score) }}>
                      {evaluation.overall_score}
                    </div>
                    <p style={{ margin: 0, fontWeight: 600 }}>{evaluation.summary_text}</p>
                  </div>

                  {evaluation.strengths.length > 0 && (
                    <div>
                      <div className="page-kicker">优点</div>
                      <ul className="mini-bullets">
                        {evaluation.strengths.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}
                  {evaluation.weaknesses.length > 0 && (
                    <div>
                      <div className="page-kicker">待改进</div>
                      <ul className="mini-bullets mini-bullets--warn">
                        {evaluation.weaknesses.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}
                  {evaluation.missing_sections.length > 0 && (
                    <div>
                      <div className="page-kicker">缺失模块</div>
                      <div className="job-tags">
                        {evaluation.missing_sections.map((s) => <span key={s} className="tag tag--muted">{s}</span>)}
                      </div>
                    </div>
                  )}
                </div>

                <ChatPanel
                  step="evaluate"
                  context={evaluation}
                  profileName={profile?.name}
                  title="讨论评估结果"
                  placeholder="问 AI 如何改进简历..."
                  onApply={(msgs) => onEvaluate(msgs)}
                />
              </section>
            )}

            {/* Step 3: JD 分析按钮 */}
            {evaluation && !jdAnalysis && selectedJob && (
              <div className="toolbar-row">
                <button type="button" className="button-primary" onClick={() => onAnalyzeJD()} disabled={loading !== ""}>
                  {loading === "analyze" ? "AI 分析 JD 中..." : "Step 3: AI 分析目标岗位 JD"}
                </button>
              </div>
            )}
            {evaluation && !selectedJob && (
              <div className="empty-state">
                <strong>需要先选择目标岗位</strong>
                <p>请切换到「岗位」页，选择一个岗位，再回到这里继续。</p>
              </div>
            )}

            {/* JD 分析结果 */}
            {jdAnalysis && (
              <section className="panel panel-muted">
                <div className="panel-inner section-grid">
                  <div className="page-kicker" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>AI 岗位 JD 分析</span>
                    <button type="button" className="button-secondary" onClick={() => onAnalyzeJD()} disabled={loading !== ""} style={{ fontSize: 12, padding: '4px 10px' }}>
                      {loading === "analyze" ? "分析中..." : "🔄 重新分析"}
                    </button>
                  </div>
                  <p style={{ fontWeight: 600 }}>{jdAnalysis.summary_text}</p>

                  <JDCategory label="必备技能" items={jdAnalysis.must_have_skills} />
                  <JDCategory label="加分技能" items={jdAnalysis.nice_to_have_skills} variant="muted" />
                  <JDCategory label="经验要求" items={jdAnalysis.experience_requirements} variant="outline" />
                  <JDCategory label="软技能" items={jdAnalysis.soft_skills} variant="outline" />
                  <JDCategory label="领域知识" items={jdAnalysis.domain_knowledge} variant="outline" />

                  {jdAnalysis.education_requirements && (
                    <div className="mini-row">
                      <span>学历要求</span>
                      <strong>{jdAnalysis.education_requirements}</strong>
                    </div>
                  )}
                </div>

                <ChatPanel
                  step="analyze"
                  context={jdAnalysis}
                  profileName={profile?.name}
                  title="讨论 JD 分析"
                  placeholder="问 AI 这个岗位看重什么..."
                  onApply={(msgs) => onAnalyzeJD(msgs)}
                />
              </section>
            )}

            {/* Step 4: 优化按钮 */}
            {jdAnalysis && !optimization && (
              <div className="toolbar-row">
                <button type="button" className="button-primary" onClick={() => onOptimize()} disabled={loading !== ""}>
                  {loading === "optimize" ? "AI 优化中..." : "Step 4: AI 生成优化方案"}
                </button>
              </div>
            )}

            {/* 优化结果 — 完整定制简历 */}
            {optimization && (
              <section className="panel panel-muted">
                <div className="panel-inner section-grid">
                  <div className="page-kicker" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>📋 定制化简历预览</span>
                    <button type="button" className="button-secondary" onClick={() => onOptimize()} disabled={loading !== ""} style={{ fontSize: 12, padding: '4px 10px' }}>
                        {loading === "optimize" ? "优化中..." : "🔄 重新优化"}
                      </button>
                  </div>
                  <p className="page-copy" style={{ fontWeight: 600 }}>{optimization.summary}</p>

                  {/* 个人总结 */}
                  {optimization.tailored_summary && (
                    <div>
                      <div className="page-kicker">个人总结</div>
                      <div className="detail-jd"><p>{optimization.tailored_summary}</p></div>
                    </div>
                  )}

                  {/* 技能展示 */}
                  {optimization.skills_display && optimization.skills_display.length > 0 && (
                    <div>
                      <div className="page-kicker">专业技能</div>
                      <div className="job-tags">
                        {optimization.skills_display.map((s: string) => <span key={s} className="tag">{s}</span>)}
                      </div>
                    </div>
                  )}

                  {/* 优化后的工作经历（新版结构化） */}
                  {optimization.work_experience && optimization.work_experience.length > 0 && (
                    <div>
                      <div className="page-kicker">工作经历（AI 优化版）</div>
                      {optimization.work_experience.map((exp: any, ei: number) => (
                        <div key={ei} style={{ marginBottom: 12 }}>
                          <p style={{ fontWeight: 700, margin: 0, fontSize: 14 }}>
                            {exp.title} <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>@ {exp.company} · {exp.duration}</span>
                          </p>
                          <ul className="mini-bullets" style={{ marginTop: 4 }}>
                            {(exp.bullets || []).map((b: string, bi: number) => (
                              <li key={bi}>{b}</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 优化后的项目经历 */}
                  {optimization.projects && optimization.projects.length > 0 && (
                    <div>
                      <div className="page-kicker">项目经历（AI 优化版）</div>
                      {optimization.projects.map((proj: any, pi: number) => (
                        <div key={pi} style={{ marginBottom: 8 }}>
                          <p style={{ fontWeight: 700, margin: 0, fontSize: 14 }}>
                            {proj.name}
                            {proj.technologies && proj.technologies.length > 0 && (
                              <span style={{ fontWeight: 400, color: 'var(--accent)', fontSize: 13 }}>
                                {' '}[{proj.technologies.join(' · ')}]
                              </span>
                            )}
                          </p>
                          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text)' }}>{proj.description}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 匹配/缺失技能 */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    {optimization.matched_skills.length > 0 && (
                      <div>
                        <div className="page-kicker">已匹配技能</div>
                        <div className="job-tags">
                          {optimization.matched_skills.map((s: string) => <span key={s} className="tag">{s}</span>)}
                        </div>
                      </div>
                    )}
                    {optimization.missing_skills.length > 0 && (
                      <div>
                        <div className="page-kicker">待补充技能</div>
                        <div className="job-tags">
                          {optimization.missing_skills.map((s: string) => (
                            <span key={s} className="tag" style={{ background: "rgba(154,52,18,0.1)", color: "var(--warning)" }}>{s}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {optimization.gap_strategies.length > 0 && (
                    <div>
                      <div className="page-kicker">弥补建议</div>
                      <ul className="mini-bullets mini-bullets--warn">
                        {optimization.gap_strategies.map((g: string, i: number) => <li key={i}>{g}</li>)}
                      </ul>
                    </div>
                  )}
                </div>

                <ChatPanel
                  step="optimize"
                  context={optimization}
                  profileName={profile?.name}
                  title="讨论优化方案"
                  placeholder="问 AI 如何进一步修改..."
                  onApply={(msgs) => onOptimize(msgs)}
                />
              </section>
            )}

            {/* Step 5: 生成最终简历 — JadeAI 风格预览 */}
            {optimization && (
              <section className="panel panel-strong" style={{ border: '2px solid var(--accent)', overflow: 'hidden' }}>
                <div style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)', padding: '14px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: '#e94560', fontWeight: 700, fontSize: 13 }}>📋 最终简历预览 · JadeAI 现代模板</span>
                  <button type="button" className="button-primary" onClick={onDownload} disabled={downloading || !optimization}
                    style={{ background: '#e94560', border: 'none', fontSize: 13, padding: '8px 20px', borderRadius: 8 }}>
                    {downloading ? '生成中...' : '📥 下载 PDF'}
                  </button>
                </div>

                {/* 简历预览 — JadeAI Modern 风格 */}
                <div style={{display:"flex",justifyContent:"center"}}><div id="resume-preview-print" style={{width:794,background:"#fff",overflow:"hidden"}}>
                <div style={{ padding: 20 }}>
                  {/* 头部 */}
                  <div style={{ background: 'linear-gradient(135deg, #1a1a2e, #0f3460)', borderRadius: '12px 12px 0 0', padding: '20px 24px', color: '#fff', position: 'relative', overflow: 'hidden' }}>
                    <div style={{ position: 'absolute', right: -20, top: -20, width: 80, height: 80, borderRadius: '50%', background: 'radial-gradient(circle, #e94560 0%, transparent 70%)', opacity: 0.15 }} />
                    <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5 }}>{profile?.name || '姓名'}</div>
                    <div style={{ color: '#e94560', fontSize: 13, marginTop: 2, fontWeight: 500 }}>{profile?.title || selectedJob?.title || ''}</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', marginTop: 10, fontSize: 12, color: '#b0c4de' }}>
                      {profile?.phone && <span>📞 {profile.phone}</span>}
                      {profile?.email && <span>✉ {profile.email}</span>}
                      {profile?.location && <span>📍 {profile.location}</span>}
                      {profile?.birth && <span>{profile.birth}</span>}
                    </div>
                  </div>

                  {/* 内容区 */}
                  <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderTop: 0, borderRadius: '0 0 12px 12px', padding: '18px 24px' }}>
                    {/* 总结 */}
                    {optimization.tailored_summary && (
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                          <span style={{ width: 24, height: 3, borderRadius: 2, background: 'linear-gradient(90deg, #e94560, #0f3460)' }} />
                          <span style={{ fontWeight: 700, fontSize: 12, color: '#e94560', textTransform: 'uppercase', letterSpacing: 1 }}>个人总结</span>
                        </div>
                        <p style={{ fontSize: 13, lineHeight: 1.8, color: '#4b5563', margin: 0 }}>{optimization.tailored_summary}</p>
                      </div>
                    )}

                    {/* 技能 */}
                    {optimization.skills_display && optimization.skills_display.length > 0 && (
                      <div style={{ marginBottom: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                          <span style={{ width: 24, height: 3, borderRadius: 2, background: 'linear-gradient(90deg, #e94560, #0f3460)' }} />
                          <span style={{ fontWeight: 700, fontSize: 12, color: '#e94560', textTransform: 'uppercase', letterSpacing: 1 }}>技能</span>
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {optimization.skills_display.map((s: string) => (
                            <span key={s} style={{ background: '#f3f4f6', borderRadius: 20, padding: '3px 12px', fontSize: 12, color: '#374151' }}>{s}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 工作经历 */}
                    {optimization.work_experience && optimization.work_experience.length > 0 && (
                      <div style={{ marginBottom: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                          <span style={{ width: 24, height: 3, borderRadius: 2, background: 'linear-gradient(90deg, #e94560, #0f3460)' }} />
                          <span style={{ fontWeight: 700, fontSize: 12, color: '#e94560', textTransform: 'uppercase', letterSpacing: 1 }}>工作经历</span>
                        </div>
                        {optimization.work_experience.slice(0, 4).map((exp: any, i: number) => (
                          <div key={i} style={{ borderLeft: '2px solid #e94560', paddingLeft: 12, marginBottom: 12 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                              <span style={{ fontWeight: 600, fontSize: 13 }}>{exp.title}</span>
                              <span style={{ fontSize: 11, color: '#9ca3af', background: '#f3f4f6', borderRadius: 10, padding: '2px 8px' }}>{exp.duration}</span>
                            </div>
                            <div style={{ fontSize: 12, color: '#e94560', fontWeight: 500 }}>{exp.company}</div>
                            {(exp.bullets || []).slice(0, 3).map((b: string, j: number) => (
                              <div key={j} style={{ fontSize: 12, lineHeight: 1.7, color: '#4b5563', marginTop: 3 }}>• {b}</div>
                            ))}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 项目经历 */}
                    {optimization.projects && optimization.projects.length > 0 && (
                      <div style={{ marginBottom: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                          <span style={{ width: 24, height: 3, borderRadius: 2, background: 'linear-gradient(90deg, #e94560, #0f3460)' }} />
                          <span style={{ fontWeight: 700, fontSize: 12, color: '#e94560', textTransform: 'uppercase', letterSpacing: 1 }}>项目经历</span>
                        </div>
                        {optimization.projects.slice(0, 4).map((proj: any, i: number) => (
                          <div key={i} style={{ borderLeft: '2px solid #0f3460', paddingLeft: 12, marginBottom: 10 }}>
                            <div style={{ fontWeight: 600, fontSize: 13 }}>
                              {proj.name}
                              {proj.technologies && proj.technologies.length > 0 && (
                                <span style={{ fontWeight: 400, color: '#0f3460', fontSize: 11, marginLeft: 6 }}>
                                  [{proj.technologies.join(' · ')}]
                                </span>
                              )}
                            </div>
                            {proj.description && (
                              <div style={{ fontSize: 12, lineHeight: 1.7, color: '#4b5563', marginTop: 2 }}>{proj.description}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 教育背景 */}
                    {profile?.education && profile.education.length > 0 && (
                      <div style={{ marginBottom: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                          <span style={{ width: 24, height: 3, borderRadius: 2, background: 'linear-gradient(90deg, #e94560, #0f3460)' }} />
                          <span style={{ fontWeight: 700, fontSize: 12, color: '#e94560', textTransform: 'uppercase', letterSpacing: 1 }}>教育背景</span>
                        </div>
                        {profile.education.map((edu: any, i: number) => (
                          <div key={i} style={{ fontSize: 12, color: '#4b5563', marginBottom: 2 }}>
                            {[edu.institution, edu.degree, edu.major, edu.graduation].filter(Boolean).join(' · ')}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                </div></div>
              </section>
            )}
          </div>

          {/* === 右侧信息栏 === */}
          <aside style={{width:280,flexShrink:0,position:"sticky",top:20,maxHeight:"calc(100vh - 40px)",overflowY:"auto",display:"grid",gap:12}}>
            <div className="metric-grid">
              <div className="metric-card">
                <span className="metric-card__label">简历</span>
                <span className="metric-card__value">{profile ? "已解析" : "未上传"}</span>
              </div>
              <div className="metric-card">
                <span className="metric-card__label">评分</span>
                <span className="metric-card__value mono" style={{ color: evaluation ? scoreColor(evaluation.overall_score) : undefined }}>
                  {evaluation ? `${evaluation.overall_score}/100` : "-"}
                </span>
              </div>
              <div className="metric-card">
                <span className="metric-card__label">建议</span>
                <span className="metric-card__value mono">{optimization?.optimized_bullets?.length ?? "-"}</span>
              </div>
            </div>

            {/* 附件管理 */}
            <div className="panel panel-muted">
              <div className="panel-inner section-grid">
                <div className="page-kicker">附件管理</div>
                {uploadedFiles.length === 0 ? (
                  <p className="workspace-target-meta" style={{ fontSize: 12 }}>暂无上传的简历</p>
                ) : (
                  <div style={{ display: 'grid', gap: 6 }}>
                    {uploadedFiles.slice(0, 8).map(f => (
                      <div key={f.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                        <span
                          onClick={() => onLoadResume(f.id)}
                          style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: 'pointer', color: 'var(--accent)', flex: 1 }}
                          title="点击加载此简历"
                        >{f.filename}</span>
                        <button type="button" className="chat-header__clear" onClick={() => onDeleteFile(f.id)} title="删除">✕</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </div>
            {/* 目标岗位 */}
            <div className="panel panel-muted">
              <div className="panel-inner section-grid">
                <div className="page-kicker">目标岗位</div>
                {selectedJob ? (
                  <div className="stack">
                    <h3 className="workspace-target-title">{selectedJob.title}</h3>
                    <p className="workspace-target-meta">{selectedJob.company} · {selectedJob.city} · {selectedJob.salary}</p>
                    <p className="workspace-target-meta" style={{ fontSize: 12 }}>
                      JD: {selectedJob.jd_text ? `${selectedJob.jd_text.length}字符` : "未补充"}
                    </p>
                  </div>
                ) : (
                  <div className="empty-state"><strong>未选择</strong><p>去「岗位」页选一个。</p></div>
                )}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}

/** 辅助组件：JD 分类展示 */
function JDCategory({ label, items, variant = "default" }: { label: string; items: string[]; variant?: string }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <div className="page-kicker">{label}</div>
      <div className="job-tags">
        {items.map((s) => (
          <span key={s} className={`tag ${variant === "muted" ? "tag--muted" : ""}`}>{s}</span>
        ))}
      </div>
    </div>
  );
}


/** 可编辑字段行 */
function FieldRow({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 36, whiteSpace: 'nowrap' }}>{label}</span>
      <input
        className="form-input form-input--inline"
        style={{ padding: '4px 8px', fontSize: 12, borderRadius: 8 }}
        value={value}
        onChange={e => onChange(e.target.value)}
      />
    </div>
  );
}
