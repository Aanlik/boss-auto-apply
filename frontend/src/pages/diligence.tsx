import { useState } from "react";
import { evaluateCompany } from "../lib/api";

export default function DiligencePage() {
  const [name, setName] = useState("某公司");
  const [industry, setIndustry] = useState("AI");
  const [summary, setSummary] = useState("");
  const [risk, setRisk] = useState("");
  const [outlook, setOutlook] = useState("");
  const [evidence, setEvidence] = useState<string[]>([]);

  async function evaluate() {
    const data = await evaluateCompany({
      name,
      industry,
      description: `${industry} 成长中`,
    });
    setSummary(data.summary || "");
    setRisk(data.risk || "");
    setOutlook(data.outlook || "");
    setEvidence(data.evidence || []);
  }

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">公司尽调</p>
          <h2 className="page-title">用互联网信息和 AI 生成可解释的公司判断</h2>
          <p className="page-copy">输入公司名后，先做资料整合，再回到这里看风险、前景和证据。</p>
        </div>
        <div className="tag">入口：岗位页、排序页、详情区</div>
      </div>

      <div className="panel panel-strong">
        <div className="panel-inner section-grid">
          <div className="toolbar-row">
            <label className="field">
              <span className="field-label">公司名</span>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="公司名" />
            </label>
            <label className="field">
              <span className="field-label">行业</span>
              <input value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="行业" />
            </label>
          </div>
          <div className="toolbar-row">
            <button type="button" className="button-primary" onClick={evaluate}>
              生成尽调摘要
            </button>
          </div>

          <div className="summary-grid">
            <div className="panel panel-muted">
              <div className="panel-inner section-grid">
                <div className="page-kicker">摘要</div>
                <p className="page-copy">{summary || "尽调完成后会显示结论。"}</p>
                <p className="workspace-target-meta mono">风险：{risk || "待生成"}</p>
                <p className="workspace-target-meta mono">前景：{outlook || "待生成"}</p>
              </div>
            </div>
            {evidence.length > 0 ? (
              <div className="panel panel-muted">
                <div className="panel-inner section-grid">
                  <div className="page-kicker">证据</div>
                  <ul className="list-reset summary-list">
                    {evidence.map((item) => (
                      <li key={item} className="workspace-target-meta">
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <strong>还没有证据</strong>
                <p>点击“生成尽调摘要”后，互联网信息会在这里整合出来。</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
