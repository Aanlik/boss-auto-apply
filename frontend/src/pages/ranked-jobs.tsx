import { useState } from "react";
import { rankJobs } from "../lib/api";

const sampleJobs = [
  { title: "Python 后端工程师", company: "A 公司", city: "深圳", salary: "20-30K" },
  { title: "前端工程师", company: "B 公司", city: "北京", salary: "15-25K" },
];

export default function RankedJobsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [status, setStatus] = useState("");

  async function refresh() {
    setStatus("排序中...");
    const data = await rankJobs(
      sampleJobs,
      { skills: ["Python"], title: "Python 后端工程师" },
      { "A 公司": { risk: "low", outlook: "positive" } },
    );
    setItems(data.jobs || []);
    setStatus(`已排序 ${data.jobs?.length || 0} 条`);
  }

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">排序结果</p>
          <h2 className="page-title">把岗位、公司和行业分数排成一列</h2>
          <p className="page-copy">这里展示综合分和排序位置，方便你快速扫一遍再决定是否投递。</p>
        </div>
        <div className={`status-line ${status.includes("已排序") ? "status-line--success" : ""}`}>{status || "等待刷新"}</div>
      </div>

      <div className="panel panel-strong">
        <div className="panel-inner section-grid">
          <div className="toolbar-row">
            <button type="button" className="button-primary" onClick={refresh}>
              刷新排序
            </button>
          </div>

          {items.length > 0 ? (
            <ul className="list-reset job-grid">
              {items.map((job) => (
                <li key={`${job.title}-${job.company}`} className="job-card">
                  <div className="job-card__top">
                    <div className="stack">
                      <h3 className="job-card__title">{job.title}</h3>
                      <p className="job-card__meta">{job.company}</p>
                    </div>
                    <span className="tag mono">总分 {job.total_score}</span>
                  </div>
                  <p className="workspace-target-meta">位置：{job.rank_index}</p>
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state">
              <strong>还没有排序结果</strong>
              <p>先点击“刷新排序”，看看综合分怎么排。</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
