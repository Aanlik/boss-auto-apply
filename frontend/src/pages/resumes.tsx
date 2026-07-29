import { useState, useEffect, useRef, useCallback, type ChangeEvent } from "react";
import {
  parseResumeFile, evaluateResume, listUploadedFiles, reEnrichResume,
  deleteUploadedFile, loadResume, getActiveResume, updateProfile
  , listResumeVersions, saveResumeVersion, compareResumeVersions, listPdfTemplates, getPdfPreviewOptions, exportResumePdf, previewResumePdf
} from "../lib/api";
import type { UploadedFile, ResumeProfile, ResumeEvaluation, ResumeVersion } from "../lib/types";
import { useWorkflowState, useWorkflowDispatch, actions } from "../lib/store";
import ChatPanel from "../components/ChatPanel";
import { ErrorBanner } from "../components/SharedUI";

function parseCompleteness(profile: ResumeProfile | null): string {
  if (!profile) return "";
  const checks = [profile.name, profile.title, profile.phone, profile.email, profile.location, profile.summary, profile.skills?.length, profile.work_experience?.length, profile.education?.length];
  const filled = checks.filter(v => (typeof v === "number" ? v > 0 : !!v)).length;
  const pct = Math.round((filled / checks.length) * 100);
  return `${pct >= 80 ? "完整" : pct >= 50 ? "部分" : "待完善"} · ${filled}/${checks.length}`;
}

const LABEL: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: "var(--text-muted)", marginBottom: 3, display: "block" };
const CARD: React.CSSProperties = { padding: 10, border: "1px solid var(--border)", borderRadius: 8, marginTop: 8 };
const CARD_ROW: React.CSSProperties = { display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" as const };
const GRID: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 };

export default function ResumesPage() {
  const { resumeProfile, uploadedFiles: propFiles } = useWorkflowState();
  const dispatch = useWorkflowDispatch();

  const [profile, setProfile] = useState<ResumeProfile | null>(resumeProfile);
  const [fileId, setFileId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [files, setFiles] = useState<UploadedFile[]>(propFiles.length > 0 ? propFiles : []);
  const [evaluation, setEvaluation] = useState<ResumeEvaluation | null>(null);
  const [parsing, setParsing] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState("");
  const [evalFailed, setEvalFailed] = useState(false);
  const [parseStatus, setParseStatus] = useState("");
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [versionSummary, setVersionSummary] = useState<string[]>([]);
  const [pdfTemplates, setPdfTemplates] = useState<Record<string, { name: string; description: string; font: string; density: string; bestFor: string[]; layout: string }>>({});
  const [pdfDensityOptions, setPdfDensityOptions] = useState<Array<{ key: string; label: string; description: string }>>([]);
  const [pdfTemplate, setPdfTemplate] = useState<"modern" | "classic" | "ats">("modern");
  const [pdfDensity, setPdfDensity] = useState("balanced");
  const [pdfStatus, setPdfStatus] = useState("");
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState("");

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadIdRef = useRef(0);
  const pollingRef = useRef("");
  const evalRef = useRef("");
  const mountedRef = useRef(true);
  const initDoneRef = useRef(false);

  const autoSave = useCallback((p: ResumeProfile) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    const fid = fileId;  // 捕获调用时的 fileId
    saveTimer.current = setTimeout(() => { if (mountedRef.current) updateProfile(p, fid).catch((e: unknown) => { console.warn('[autoSave] 保存失败:', e); }); }, 800);
  }, [fileId]);

  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false; if (saveTimer.current) clearTimeout(saveTimer.current); }; }, []);
  useEffect(() => { dispatch(actions.setResumeProfile(profile)); }, [profile]);
  useEffect(() => { dispatch(actions.setUploadedFiles(files)); }, [files]);

  // ── 初始化 ──
  useEffect(() => {
    if (initDoneRef.current) return; initDoneRef.current = true;
    let c = false;
    getActiveResume().then(d => {
      if (c || !d.profile) return;
      setProfile(d.profile); setResumeText(d.raw_text || ""); setFileId(d.file_id || ""); pollingRef.current = d.file_id || "";
      setDisplayName(d.file_id?.split("_").slice(2).join("_") || d.file_id || "");
      if (d.eval) setEvaluation(d.eval as ResumeEvaluation);
      if (d.parse_status === "pending_ai") setParseStatus("pending_ai");
      else if (d.parse_status === "ai_enriched") {
        setParseStatus("ai_enriched");
        setTimeout(() => { if (pollingRef.current === d.file_id) getActiveResume().then(x => { if (x.profile) setProfile(x.profile); setParseStatus(""); }).catch(() => {}); }, 500);
      }
    }).catch(() => {});
    listUploadedFiles().then(r => { if (!c && r.files?.length > 0) setFiles(r.files); }).catch(() => {});
    listResumeVersions().then(r => { if (!c) setVersions(r.versions || []); }).catch(() => {});
    Promise.all([listPdfTemplates(), getPdfPreviewOptions()]).then(([templates, options]) => {
      if (c) return;
      setPdfTemplates(options.templates || templates.templates || {});
      setPdfTemplate(options.defaultTemplate || templates.default || "modern");
      setPdfDensityOptions(options.densityOptions || []);
      setPdfDensity(options.defaultDensity || "balanced");
    }).catch(() => {});
    return () => { c = true; };
  }, []);

  // ── AI 轮询 ──
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (parseStatus !== "pending_ai") return;
    const target = pollingRef.current;
    if (!target) { setParseStatus(""); return; }
    const t = setInterval(() => {
      getActiveResume().then(d => {
        if (pollingRef.current !== target) return;
        if (d.parse_status && d.parse_status !== "pending_ai") {
          setParseStatus(d.parse_status);
          if (d.parse_status === "ai_enriched" && d.profile) setProfile(d.profile);
          setTimeout(() => { if (pollingRef.current === target) setParseStatus(""); }, 2000);
        }
      }).catch(() => {});
    }, 3000);
    pollIntervalRef.current = t;
    const to = setTimeout(() => { 
      if (pollIntervalRef.current) { clearInterval(pollIntervalRef.current); pollIntervalRef.current = null; }
      setParseStatus(p => p === "pending_ai" ? "" : p); 
    }, 120000);
    return () => { clearInterval(t); clearTimeout(to); pollIntervalRef.current = null; };
  }, [parseStatus]);

  // ── 上传 ──
  async function onUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    const lid = ++loadIdRef.current;
    setParseStatus(""); pollingRef.current = "";
    setFileId(file.name); setDisplayName(file.name); setParsing(true); setError(""); setEvaluation(null); setEvalFailed(false);
    try {
      const r = await parseResumeFile(file);
      if (loadIdRef.current !== lid) return;
      setProfile(r.profile); setResumeText(r.raw_text || ""); setFileId(r.file_id); pollingRef.current = r.file_id;
      const dn = r.file_id.split("_").slice(2).join("_") || file.name; setDisplayName(dn);
      if (r.parse_status === "pending_ai") setParseStatus("pending_ai");
      setFiles(p => p.some(f => f.id === r.file_id) ? p : [{ id: r.file_id, filename: dn, path: "", size: file.size, uploaded_at: new Date().toISOString() }, ...p]);
    } catch (err) { if (loadIdRef.current === lid) setError(err instanceof Error ? err.message : "解析失败"); }
    finally { if (loadIdRef.current === lid) setParsing(false); }
    e.target.value = "";
  }

  // ── 切换 ──
  async function onSwitch(id: string) {
    const lid = ++loadIdRef.current;
    if (saveTimer.current) { clearTimeout(saveTimer.current); saveTimer.current = null; }
    setParseStatus(""); pollingRef.current = ""; evalRef.current = "";
    setSwitching(true); setError(""); setEvaluation(null); setEvaluating(false); setEvalFailed(false);
    try {
      const d = await loadResume(id);
      if (loadIdRef.current !== lid) return;
      setProfile(d.profile); setResumeText(d.raw_text || ""); setFileId(id); pollingRef.current = id;
      setDisplayName(files.find(f => f.id === id)?.filename || id);
      if (d.eval) setEvaluation(d.eval as ResumeEvaluation);
      if (d.parse_status === "pending_ai") setParseStatus("pending_ai"); else setParseStatus("");
      listResumeVersions().then(r => setVersions(r.versions || [])).catch(() => {});
    } catch (err) { if (loadIdRef.current === lid) setError(err instanceof Error ? err.message : "加载失败"); }
    finally { if (loadIdRef.current === lid) setSwitching(false); }
  }

  async function onDelete(id: string) {
    await deleteUploadedFile(id).catch(() => {});
    if (saveTimer.current) { clearTimeout(saveTimer.current); saveTimer.current = null; }
    const remaining = files.filter(f => f.id !== id);
    setFiles(remaining);
    if (fileId === id) {
      // 删除的是当前活跃附件：清除左侧数据
      setProfile(null); setFileId(""); setDisplayName(""); setResumeText(""); setEvaluation(null);
      setParseStatus(""); pollingRef.current = ""; evalRef.current = ""; dispatch(actions.setResumeProfile(null));
      // 如果还有剩余附件，自动加载第一个
      if (remaining.length > 0) {
        const next = remaining[0];
        try {
          const d = await loadResume(next.id);
          if (d.profile) { setProfile(d.profile); setFileId(d.file_id || next.id); setDisplayName(next.filename); setResumeText(d.raw_text || ""); pollingRef.current = d.file_id || next.id; }
        } catch {}
      }
    }
  }

  const onEvaluate = useCallback(async () => {
    const currentProfile = profile;
    if (!currentProfile || evaluating) return;
    const evalFileId = fileId;
    evalRef.current = evalFileId;
    setError(""); setEvalFailed(false); setEvaluating(true);
    try {
      const result = await evaluateResume(currentProfile, resumeText, []);
      if (evalRef.current !== evalFileId) return; // 用户已切换简历，丢弃旧结果
      setEvaluation(result);
    } catch (err) { 
      if (evalRef.current !== evalFileId) return;
      setError(err instanceof Error ? err.message : "评估失败"); setEvalFailed(true); 
    }
    finally { 
      if (evalRef.current === evalFileId) setEvaluating(false); 
    }
  }, [profile, evaluating, fileId]);

  // ── 字段编辑 ──
  const uf = (f: string, v: string) => { if (!profile) return; const n = { ...profile, [f]: v }; setProfile(n); autoSave(n); };
  const us = (i: number, v: string) => { if (!profile) return; const s = [...profile.skills]; s[i] = v; setProfile({ ...profile, skills: s }); autoSave({ ...profile, skills: s }); };
  const as = () => { if (!profile) return; const n = { ...profile, skills: [...profile.skills, ""] }; setProfile(n); autoSave(n); };
  const rs = (i: number) => { if (!profile) return; const n = { ...profile, skills: profile.skills.filter((_, j) => j !== i) }; setProfile(n); autoSave(n); };
  const ux = (i: number, f: string, v: string) => { if (!profile) return; const e = [...profile.work_experience]; e[i] = { ...e[i], [f]: v }; setProfile({ ...profile, work_experience: e }); autoSave({ ...profile, work_experience: e }); };
  const ax = () => { if (!profile) return; const n = { ...profile, work_experience: [...profile.work_experience, { company: "", title: "", duration: "", description: "" }] }; setProfile(n); autoSave(n); };
  const rx = (i: number) => { if (!profile) return; const n = { ...profile, work_experience: profile.work_experience.filter((_, j) => j !== i) }; setProfile(n); autoSave(n); };
  const ue = (i: number, f: string, v: string) => { if (!profile) return; const e = [...profile.education]; e[i] = { ...e[i], [f]: v }; setProfile({ ...profile, education: e }); autoSave({ ...profile, education: e }); };
  const ae = () => { if (!profile) return; const n = { ...profile, education: [...profile.education, { institution: "", degree: "", major: "", graduation: "" }] }; setProfile(n); autoSave(n); };
  const re = (i: number) => { if (!profile) return; const n = { ...profile, education: profile.education.filter((_, j) => j !== i) }; setProfile(n); autoSave(n); };
  const up = (i: number, f: string, v: string) => { if (!profile) return; const e = [...profile.projects]; e[i] = { ...e[i], [f]: v }; setProfile({ ...profile, projects: e }); autoSave({ ...profile, projects: e }); };
  const ap = () => { if (!profile) return; const n = { ...profile, projects: [...profile.projects, { name: "", description: "", technologies: [] }] }; setProfile(n); autoSave(n); };
  const rp = (i: number) => { if (!profile) return; const n = { ...profile, projects: profile.projects.filter((_, j) => j !== i) }; setProfile(n); autoSave(n); };

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl);
    };
  }, [pdfPreviewUrl]);

  async function onReEnrich() {
    if (!fileId) return;
    setParseStatus("pending_ai");
    try { await reEnrichResume(); } catch (err) { setError(err instanceof Error ? err.message : "重新解析失败"); setParseStatus(""); }
  }

  async function onSaveVersion() {
    if (!profile) return;
    try {
      const r = await saveResumeVersion({ label: `手动保存 ${new Date().toLocaleString("zh-CN")}`, profile });
      setVersions(r.versions || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存版本失败");
    }
  }

  async function onCompareVersions() {
    if (versions.length < 2) return;
    try {
      const result = await compareResumeVersions({ from_index: 0, to_index: versions.length - 1 });
      setVersionSummary(result.summary || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "版本对比失败");
    }
  }

  async function onPreviewPdf() {
    if (!profile) return;
    setPdfStatus("正在生成 PDF 预览...");
    try {
      if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl);
      const url = await previewResumePdf({
        profile,
        optimization: evaluation || {},
        company: "",
        job_title: profile.title || "",
        template: pdfTemplate,
        density: pdfDensity,
      });
      setPdfPreviewUrl(url);
      setPdfStatus("PDF 预览已生成");
    } catch (err) {
      setPdfStatus(err instanceof Error ? err.message : "PDF 预览失败");
    }
  }

  async function onDownloadPdf() {
    if (!profile) return;
    setPdfStatus("正在导出 PDF...");
    try {
      await exportResumePdf({
        profile,
        optimization: evaluation || {},
        company: "",
        job_title: profile.title || "",
        template: pdfTemplate,
        density: pdfDensity,
      });
      setPdfStatus("PDF 已开始下载");
    } catch (err) {
      setPdfStatus(err instanceof Error ? err.message : "PDF 导出失败");
    }
  }

  const busy = parsing || switching;
  const comp = parseCompleteness(profile);

  return (
    <section className="stage">
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {/* ── 上传工具栏 ── */}
      <div className="toolbar-row" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <label className="button-primary" style={{ cursor: parsing ? "wait" : "pointer", opacity: parsing ? 0.6 : 1, margin: 0 }}>
            {parsing ? "解析中…" : "上传简历"}
            <input ref={fileInputRef} type="file" accept=".pdf,.docx,.png,.jpg,.jpeg" style={{ display: "none" }} onChange={onUpload} disabled={parsing} />
          </label>
          {displayName && <span style={{ fontSize: 13, color: "var(--text-muted)" }}>{displayName}</span>}
          {parseStatus === "pending_ai" && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 16px", background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 8, fontSize: 13 }}>
              <span style={{ fontSize: 16 }}>⏳</span>
              <span style={{ color: "#92400e" }}>AI 正在深度解析简历内容（技能、工作经历等），预计 10-20 秒…</span>
            </div>
          )}
          {profile && parseStatus !== "pending_ai" && (
            <button type="button" className="button-secondary" onClick={onReEnrich} style={{ fontSize: 12 }} disabled={parseStatus === "pending_ai"}>
              🔄 AI 重新解析
            </button>
          )}
          {comp && <span className="tag">{comp}</span>}
          {profile && (
            <>
              <button type="button" className="button-secondary" onClick={onSaveVersion} style={{ fontSize: 12 }}>保存版本</button>
              <button type="button" className="button-quiet" onClick={onCompareVersions} disabled={versions.length < 2} style={{ fontSize: 12 }}>对比版本</button>
              {versions.length > 0 && <span className="tag tag--muted">版本 {versions.length}</span>}
            </>
          )}
          {switching && <span className="text-muted" style={{ fontSize: 12 }}>切换中…</span>}
        </div>
      </div>

      {versionSummary.length > 0 && (
        <div className="panel panel-strong" style={{ marginBottom: 12 }}>
          <div className="panel-inner">
            <div className="page-kicker" style={{ marginBottom: 8 }}>版本对比</div>
            <div className="job-tags">
              {versionSummary.map(item => <span key={item} className="tag tag--active">{item}</span>)}
            </div>
          </div>
        </div>
      )}

      {Object.keys(pdfTemplates).length > 0 && (
        <div className="panel panel-strong" style={{ marginBottom: 12 }}>
          <div className="panel-inner">
            <div className="page-section__top" style={{ marginBottom: 8 }}>
              <div>
                <div className="page-kicker">PDF 模板</div>
                <p className="capture-panel-copy">选择后会用于当前简历的 PDF 预览和下载。</p>
              </div>
              <div className="toolbar-row toolbar-row--wrap">
                <button type="button" className="button-secondary button-secondary--sm" onClick={onPreviewPdf} disabled={!profile}>预览 PDF</button>
                <button type="button" className="button-primary button-secondary--sm" onClick={onDownloadPdf} disabled={!profile}>下载 PDF</button>
              </div>
            </div>
            <div className="pdf-template-grid">
              {Object.entries(pdfTemplates).map(([key, tpl]) => (
                <button
                  key={key}
                  type="button"
                  className={`pdf-template-card ${pdfTemplate === key ? "pdf-template-card--active" : ""}`}
                  onClick={() => {
                    const nextTemplate = key as "modern" | "classic" | "ats";
                    setPdfTemplate(nextTemplate);
                    if (tpl.density) setPdfDensity(tpl.density);
                    setPdfStatus(`已选择 ${tpl.name}`);
                  }}
                  aria-pressed={pdfTemplate === key}
                >
                  <strong>{tpl.name}{pdfTemplate === key && <span className="pdf-template-card__mark">已选</span>}</strong>
                  <p>{tpl.description}</p>
                  <div className="job-tags">
                    <span className="tag tag--muted">{tpl.density}</span>
                    <span className="tag tag--muted">{tpl.layout}</span>
                    {tpl.bestFor.slice(0, 3).map(item => <span key={item} className="tag">{item}</span>)}
                  </div>
                </button>
              ))}
            </div>
            {pdfDensityOptions.length > 0 && (
              <div className="pdf-density-strip">
                <span>字体密度</span>
                {pdfDensityOptions.map(option => (
                  <button
                    type="button"
                    key={option.key}
                    className={pdfDensity === option.key ? "tag tag--active" : "tag tag--muted"}
                    onClick={() => setPdfDensity(option.key)}
                    title={option.description}
                  >
                    {option.label}
                  </button>
                ))}
                <small>{pdfDensityOptions.find(item => item.key === pdfDensity)?.description || "导出 PDF 前可先预览版式。"}</small>
              </div>
            )}
            {pdfStatus && <p className="settings-status">{pdfStatus}</p>}
            {pdfPreviewUrl && (
              <div className="pdf-inline-preview">
                <div className="pdf-inline-preview__top">
                  <strong>PDF 预览</strong>
                  <button type="button" className="button-quiet" onClick={() => { URL.revokeObjectURL(pdfPreviewUrl); setPdfPreviewUrl(""); }}>关闭预览</button>
                </div>
                <iframe title="简历 PDF 预览" src={pdfPreviewUrl} />
              </div>
            )}
          </div>
        </div>
      )}

      {!profile ? (
        <div className="panel panel-strong" style={{ cursor: "pointer" }} onClick={() => fileInputRef.current?.click()}>
          <div className="panel-inner" style={{ padding: "40px 24px", textAlign: "center" }}>
            <div style={{ fontSize: 36, marginBottom: 12 }}>📄</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-strong)", marginBottom: 4 }}>点击或拖拽上传简历</div>
            <div style={{ fontSize: 13, color: "var(--text-muted)" }}>支持 PDF、Word；图片简历需先配置支持视觉识别的 AI 模型</div>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
          {/* ── 左：简历详情 ── */}
          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 16 }}>
            {/* 基本信息 */}
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-section__top" style={{ marginBottom: 10 }}>
                  <div className="page-kicker">基本信息</div>
                </div>
                <div style={GRID}>
                  <div><label style={LABEL}>姓名</label><input className="form-input form-input--inline" value={profile.name} onChange={e => uf("name", e.target.value)} /></div>
                  <div><label style={LABEL}>性别</label><input className="form-input form-input--inline" value={profile.gender} onChange={e => uf("gender", e.target.value)} /></div>
                  <div><label style={LABEL}>手机号</label><input className="form-input form-input--inline" value={profile.phone} onChange={e => uf("phone", e.target.value)} /></div>
                  <div><label style={LABEL}>邮箱</label><input className="form-input form-input--inline" value={profile.email} onChange={e => uf("email", e.target.value)} /></div>
                  <div><label style={LABEL}>当前岗位</label><input className="form-input form-input--inline" value={profile.title} onChange={e => uf("title", e.target.value)} /></div>
                  <div><label style={LABEL}>所在地</label><input className="form-input form-input--inline" value={profile.location} onChange={e => uf("location", e.target.value)} /></div>
                  <div><label style={LABEL}>期望岗位</label><input className="form-input form-input--inline" value={profile.target_titles?.join("、") || ""} onChange={e => { const arr = e.target.value.split(/[、,，]/).map((s: string) => s.trim()).filter(Boolean); const n = { ...profile, target_titles: arr as any }; setProfile(n as any); autoSave(n as any); }} /></div>
                  <div><label style={LABEL}>期望城市</label><input className="form-input form-input--inline" value={profile.target_city || ""} onChange={e => uf("target_city", e.target.value)} /></div>
                  <div><label style={LABEL}>期望薪资</label><input className="form-input form-input--inline" value={profile.salary_expectation || ""} onChange={e => uf("salary_expectation", e.target.value)} placeholder="15-20K" /></div>
                </div>
              </div>
            </div>

            {/* 个人总结 + 技能 */}
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-section__top" style={{ marginBottom: 10 }}>
                  <div className="page-kicker">技能与总结</div>
                </div>
                <label style={LABEL}>个人总结</label>
                <textarea className="form-input" rows={3} value={profile.summary} onChange={e => uf("summary", e.target.value)} style={{ marginBottom: 12 }} />
                <label style={LABEL}>技能</label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {(profile.skills || []).map((s, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 2 }}>
                      <input className="form-input" style={{ width: 120, padding: "4px 8px", fontSize: 12 }} value={s} onChange={e => us(i, e.target.value)} />
                      <button type="button" className="button-quiet" onClick={() => rs(i)} style={{ color: "#e94560", padding: 2 }}>×</button>
                    </div>
                  ))}
                  <button type="button" className="button-secondary" onClick={as} style={{ fontSize: 12 }}>+ 添加技能</button>
                </div>
              </div>
            </div>

            {/* 工作经历 */}
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-section__top" style={{ marginBottom: 10 }}>
                  <div className="page-kicker">工作经历</div>
                  <button type="button" className="button-secondary" onClick={ax} style={{ fontSize: 12 }}>+ 添加</button>
                </div>
                {(profile.work_experience || []).map((exp, i) => (
                  <div key={i} style={CARD}>
                    <div style={CARD_ROW}>
                      <input className="form-input form-input--inline" value={exp.company} onChange={e => ux(i, "company", e.target.value)} placeholder="公司" style={{ flex: 1 }} />
                      <input className="form-input form-input--inline" value={exp.title} onChange={e => ux(i, "title", e.target.value)} placeholder="职位" style={{ flex: 1 }} />
                      <input className="form-input form-input--inline" value={exp.duration} onChange={e => ux(i, "duration", e.target.value)} placeholder="时间" style={{ width: 140 }} />
                      <button type="button" className="button-quiet" onClick={() => rx(i)} style={{ color: "#e94560" }}>删除</button>
                    </div>
                    <textarea className="form-input" rows={2} value={exp.description} onChange={e => ux(i, "description", e.target.value)} placeholder="工作描述…" style={{ marginTop: 6 }} />
                  </div>
                ))}
              </div>
            </div>

            {/* 教育背景 */}
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-section__top" style={{ marginBottom: 10 }}>
                  <div className="page-kicker">教育背景</div>
                  <button type="button" className="button-secondary" onClick={ae} style={{ fontSize: 12 }}>+ 添加</button>
                </div>
                {(profile.education || []).map((edu, i) => (
                  <div key={i} style={CARD}>
                    <div style={CARD_ROW}>
                      <input className="form-input form-input--inline" value={edu.institution} onChange={e => ue(i, "institution", e.target.value)} placeholder="学校" style={{ flex: 1 }} />
                      <input className="form-input form-input--inline" value={edu.degree} onChange={e => ue(i, "degree", e.target.value)} placeholder="学位" style={{ width: 120 }} />
                      <input className="form-input form-input--inline" value={edu.major} onChange={e => ue(i, "major", e.target.value)} placeholder="专业" style={{ width: 140 }} />
                      <input className="form-input form-input--inline" value={edu.graduation} onChange={e => ue(i, "graduation", e.target.value)} placeholder="时间" style={{ width: 140 }} />
                      <button type="button" className="button-quiet" onClick={() => re(i)} style={{ color: "#e94560" }}>删除</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 项目经历 */}
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-section__top" style={{ marginBottom: 10 }}>
                  <div className="page-kicker">项目经历</div>
                  <button type="button" className="button-secondary" onClick={ap} style={{ fontSize: 12 }}>+ 添加</button>
                </div>
                {(profile.projects || []).map((proj, i) => (
                  <div key={i} style={CARD}>
                    <div style={CARD_ROW}>
                      <input className="form-input form-input--inline" value={proj.name} onChange={e => up(i, "name", e.target.value)} placeholder="项目名" style={{ flex: 1 }} />
                      <input className="form-input form-input--inline" value={(proj as any).technologies?.join(", ") || ""} onChange={e => { const arr = e.target.value.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean); const projs = [...profile!.projects]; projs[i] = { ...projs[i], technologies: arr }; const n = { ...profile!, projects: projs }; setProfile(n as any); autoSave(n as any); }} placeholder="技术栈（逗号分隔）" style={{ flex: 2 }} />
                      <button type="button" className="button-quiet" onClick={() => rp(i)} style={{ color: "#e94560" }}>删除</button>
                    </div>
                    <textarea className="form-input" rows={2} value={proj.description} onChange={e => up(i, "description", e.target.value)} placeholder="项目描述…" style={{ marginTop: 6 }} />
                  </div>
                ))}
              </div>
            </div>

            {/* AI 评估 */}
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-section__top">
                  <div className="page-kicker">AI 简历评估</div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button type="button" className="button-primary" onClick={onEvaluate} disabled={evaluating}>
                      {evaluating ? "评估中…" : evaluation ? "重新评估" : "开始评估"}
                    </button>
                    {evalFailed && !evaluating && <button type="button" className="button-secondary" onClick={onEvaluate}>重试</button>}
                  </div>
                </div>
                {evaluating && (
                  <div style={{ marginTop: 12, textAlign: "center", padding: "20px 0", color: "var(--text-muted)" }}>
                    <div style={{ fontSize: 14 }}>{evaluation ? "AI 正在重新分析您的简历，请稍候…" : "AI 正在分析您的简历，请稍候…"}</div>
                  </div>
                )}
                {evaluation && !evaluating && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                      <span style={{ fontSize: 28, fontWeight: 700, color: evaluation.overall_score >= 70 ? "#16a34a" : evaluation.overall_score >= 50 ? "#d97706" : "#e94560" }}>{evaluation.overall_score}</span>
                      <span className="text-muted">/ 100 · 综合评分</span>
                    </div>
                    {evaluation.strengths?.length > 0 && (
                      <div style={{ marginTop: 8 }}><span style={{ fontSize: 13, fontWeight: 600, color: "#16a34a" }}>优势</span><ul className="list-reset" style={{ margin: "4px 0", paddingLeft: 18 }}>{evaluation.strengths.map((s, i) => <li key={i} style={{ fontSize: 13 }}>{s}</li>)}</ul></div>
                    )}
                    {evaluation.weaknesses?.length > 0 && (
                      <div style={{ marginTop: 8 }}><span style={{ fontSize: 13, fontWeight: 600, color: "#e94560" }}>待改进</span><ul className="list-reset" style={{ margin: "4px 0", paddingLeft: 18 }}>{evaluation.weaknesses.map((w, i) => <li key={i} style={{ fontSize: 13 }}>{w}</li>)}</ul></div>
                    )}
                    {evaluation.missing_sections?.length > 0 && (
                      <div style={{ marginTop: 8 }}><span style={{ fontSize: 13, fontWeight: 600, color: "#d97706" }}>缺失模块</span><ul className="list-reset" style={{ margin: "4px 0", paddingLeft: 18 }}>{evaluation.missing_sections.map((s, i) => <li key={i} style={{ fontSize: 13 }}>{s}</li>)}</ul></div>
                    )}
                    {evaluation.summary_text && (
                      <div style={{ marginTop: 16 }}>
                        <ChatPanel chatKey={`resume-eval-${fileId}`} step="evaluate" context={profile} profileName={profile?.name} title="AI 评估对话" placeholder="与 AI 讨论评估结果…"
                          onApply={async (msgs) => { const chatFileId = fileId; try { const r = await evaluateResume(profile, resumeText, msgs); if (chatFileId === fileId) setEvaluation(r); } catch { setError("评估对话失败"); } }} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── 右：附件管理 ── */}
          <div className="workbench-rail" style={{ width: 220, flexShrink: 0 }}>
            <div className="panel panel-strong">
              <div className="panel-inner">
                <div className="page-kicker" style={{ marginBottom: 12 }}>附件管理</div>
                {files.length === 0 ? (
                  <div style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center", padding: "16px 0" }}>暂无附件</div>
                ) : (
                  <div className="mini-list">
                    {files.map(f => (
                      <div key={f.id} className={`file-item ${fileId === f.id ? "file-item--active" : ""}`} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 10px", background: fileId === f.id ? "var(--surface-muted)" : "transparent" }}>
                        <span style={{ fontSize: 13, cursor: switching ? "wait" : "pointer", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                          onClick={() => { if (!switching) onSwitch(f.id); }} title={f.filename}>{f.filename}</span>
                        <button type="button" className="button-quiet" onClick={() => onDelete(f.id)} style={{ color: "#e94560", flexShrink: 0 }}>删除</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
