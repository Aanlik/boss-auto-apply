import { useState } from "react";
import { draftMessage, reviseMessage } from "../lib/api";

export default function MessagesPage() {
  const [jobTitle, setJobTitle] = useState("Python 后端工程师");
  const [resumeSummary, setResumeSummary] = useState("3 年 Python 后端经验");
  const [companySummary, setCompanySummary] = useState("成长型公司");
  const [draft, setDraft] = useState("");

  async function generate() {
    const data = await draftMessage({
      job_title: jobTitle,
      resume_summary: resumeSummary,
      company_summary: companySummary,
    });
    setDraft(data.draft || "");
  }

  async function revise() {
    const data = await reviseMessage({
      draft,
      edit_hint: "更简洁一点",
    });
    setDraft(data.draft || "");
  }

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">打招呼语</p>
          <h2 className="page-title">按岗位自动生成，再人工收口</h2>
          <p className="page-copy">把岗位标题、简历摘要和公司摘要放进来，先出草稿，再按你的口味改一遍。</p>
        </div>
        <div className="tag">人工确认后再发送</div>
      </div>

      <div className="panel panel-strong">
        <div className="panel-inner section-grid">
          <div className="toolbar-row">
            <label className="field">
              <span className="field-label">岗位名称</span>
              <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} placeholder="岗位名称" />
            </label>
            <label className="field">
              <span className="field-label">简历摘要</span>
              <input value={resumeSummary} onChange={(e) => setResumeSummary(e.target.value)} placeholder="简历摘要" />
            </label>
            <label className="field">
              <span className="field-label">公司摘要</span>
              <input value={companySummary} onChange={(e) => setCompanySummary(e.target.value)} placeholder="公司摘要" />
            </label>
          </div>
          <div className="toolbar-row">
            <button type="button" className="button-primary" onClick={generate}>
              生成草稿
            </button>
            <button type="button" className="button-secondary" onClick={revise} disabled={!draft}>
              按建议改写
            </button>
          </div>
          <div className="summary-grid">
            <label className="field">
              <span className="field-label">草稿</span>
              <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={8} />
            </label>
            <div className="empty-state">
              <strong>编辑提示</strong>
              <p>可以更短一点，或者加一点岗位关键词，保持自然就行。</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
