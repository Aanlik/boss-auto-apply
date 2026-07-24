import { useState } from "react";
import { buildInbox, confirmSend } from "../lib/api";

export default function InboxPage() {
  const [items, setItems] = useState<any[]>([]);
  const [status, setStatus] = useState("");

  async function refresh() {
    const data = await buildInbox({
      jobs: [
        { title: "Python 后端工程师", company: "A 公司", draft: "您好，我在后端工程方向有较多实践。", manual_confirmed: false },
        { title: "产品经理", company: "B 公司", draft: "您好，我对产品方向很感兴趣。", manual_confirmed: false },
      ],
    });
    setItems(data.items || []);
    setStatus(`已加载 ${data.items?.length || 0} 条`);
  }

  async function confirm(index: number) {
    const item = items[index];
    const data = await confirmSend({
      job: {
        title: item.job_title,
        company: item.company,
        manual_confirmed: true,
      },
    });
    setItems((current) =>
      current.map((row, i) =>
        i === index ? { ...row, status: data.status, note: data.note, manual_confirmed: true } : row,
      ),
    );
  }

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">待发送箱</p>
          <h2 className="page-title">所有发送都要经过这里</h2>
          <p className="page-copy">这里是最后一步，先看草稿，再人工确认，确认后才算真正发出。</p>
        </div>
        <div className={`status-line ${status.includes("已加载") ? "status-line--success" : ""}`}>{status || "等待加载"}</div>
      </div>

      <div className="panel panel-strong">
        <div className="panel-inner section-grid">
          <div className="toolbar-row">
            <button type="button" className="button-primary" onClick={refresh}>
              刷新待发送箱
            </button>
          </div>

          {items.length > 0 ? (
            <ul className="list-reset job-grid">
              {items.map((item, index) => (
                <li key={`${item.title}-${item.company}`} className="job-card">
                  <div className="job-card__top">
                    <div className="stack">
                      <h3 className="job-card__title">{item.job_title}</h3>
                      <p className="job-card__meta">{item.company}</p>
                    </div>
                    <span className="tag">{item.manual_confirmed ? "已确认" : "待确认"}</span>
                  </div>
                  <textarea value={item.draft} readOnly rows={4} />
                  <div className="toolbar-row">
                    <button type="button" className="button-secondary" onClick={() => confirm(index)} disabled={item.manual_confirmed}>
                      {item.manual_confirmed ? "已确认" : "人工确认发送"}
                    </button>
                  </div>
                  <p className="workspace-target-meta">{item.note || item.status}</p>
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state">
              <strong>待发送箱是空的</strong>
              <p>先去生成话术，再回来确认发送。</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
