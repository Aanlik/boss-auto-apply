import { useEffect, useState } from "react";
import { bossLogin, captureBossJobs, captureJobs, filterJobPool, listJobPool, addManualJob, deleteJob, clearAllJobs, enrichJobDetails } from "../lib/api";
import type { JobPosting } from "../lib/types";

interface JobsPageProps {
  selectedJobId: string | null;
  onSelectJob: (job: JobPosting) => void;
}

/** JD 详情弹窗 */
function JobDetailModal({ job, onClose }: { job: JobPosting; onClose: () => void }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel modal-panel--wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="stack">
            <p className="page-kicker">岗位详情</p>
            <h2 className="modal-title">{job.title}</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>
        <div className="modal-body">
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">公司</span>
              <span className="detail-value">{job.company}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">城市</span>
              <span className="detail-value">{job.city}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">薪资</span>
              <span className="detail-value">{job.salary}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">来源</span>
              <span className="detail-value">{job.source === "captured" ? "BOSS 抓取" : job.source === "manual" ? "手动录入" : job.source}</span>
            </div>
          </div>

          {job.keywords && job.keywords.length > 0 && (
            <div className="detail-section">
              <h4 className="detail-section-title">关键词</h4>
              <div className="job-tags">
                {job.keywords.map((k: string) => (
                  <span key={k} className="tag">{k}</span>
                ))}
              </div>
            </div>
          )}

          <div className="detail-section">
            <h4 className="detail-section-title">JD 描述</h4>
            <div className="detail-jd">
              {job.jd_text ? (
                job.jd_text.split("\n").map((line, i) => (
                  <p key={i} className={/^[\s]*$/.test(line) ? "detail-jd__spacer" : ""}>{line || "\u00A0"}</p>
                ))
              ) : (
                <p className="text-muted">暂无详细 JD</p>
              )}
            </div>
          </div>

          {job.structured_summary && (
            <div className="detail-section">
              <h4 className="detail-section-title">结构化摘要</h4>
              <p>{job.structured_summary}</p>
            </div>
          )}

          {job.source_url && (
            <div className="detail-section">
              <a href={job.source_url} target="_blank" rel="noopener noreferrer" className="link-external">
                在 Boss 直聘查看原岗位 →
              </a>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button type="button" className="button-secondary" onClick={onClose}>关闭</button>
        </div>
      </div>
    </div>
  );
}

export default function JobsPage({ selectedJobId, onSelectJob }: JobsPageProps) {
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState("");
  const [cityFilter, setCityFilter] = useState("");
  const [minSalary, setMinSalary] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Boss 抓取配置
  const [showBoss, setShowBoss] = useState(false);
  const [bossKeyword, setBossKeyword] = useState("Python");
  const [bossCity, setBossCity] = useState("深圳");
  const [bossPages, setBossPages] = useState("3");

  // 手动录入
  const [showManual, setShowManual] = useState(false);
  const [manualTitle, setManualTitle] = useState("");
  const [manualCompany, setManualCompany] = useState("");
  const [manualCity, setManualCity] = useState("");
  const [manualSalary, setManualSalary] = useState("");
  const [manualJD, setManualJD] = useState("");

  // JD 详情弹窗
  const [detailJob, setDetailJob] = useState<JobPosting | null>(null);

  // 确认清空
  const [confirmClear, setConfirmClear] = useState(false);

  async function loadJobs() {
    setLoading(true);
    setError("");
    try {
      const data = await listJobPool();
      setJobs(data.jobs);
      setTotal(data.total);
      setStatus(data.total > 0 ? `共 ${data.total} 个岗位` : "岗位池为空");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadJobs();
  }, []);

  async function onCapture() {
    setLoading(true);
    setError("");
    try {
      const data = await captureJobs();
      setStatus(`示例数据 ${data.captured} 条，共 ${data.total} 条`);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "抓取失败");
    } finally {
      setLoading(false);
    }
  }

  async function onBossLogin() {
    setLoading(true);
    setError("");
    setStatus("正在打开浏览器，请在弹出窗口中登录 Boss 直聘...");
    try {
      const result = await bossLogin();
      if (result.status === "ok") {
        setStatus("登录成功！现在可以开始抓取了");
      } else if (result.status === "timeout") {
        setStatus("登录超时，请重试");
      } else {
        setStatus(result.message || "登录完成");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  async function onCaptureBoss() {
    setLoading(true);
    setError("");
    try {
      const data = await captureBossJobs({
        keyword: bossKeyword,
        city: bossCity,
        max_pages: Number(bossPages),
      });
      setStatus(`Boss 抓取 ${data.captured} 条，共 ${data.total} 条`);
      setShowBoss(false);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Boss 抓取失败");
    } finally {
      setLoading(false);
    }
  }

  async function onFilter() {
    setLoading(true);
    setError("");
    try {
      const data = await filterJobPool({
        keywords: keyword ? [keyword] : [],
        city: cityFilter || undefined,
        min_salary: minSalary ? Number(minSalary) : undefined,
      });
      setJobs(data.jobs);
      setTotal(data.total);
      setStatus(`筛选出 ${data.total} 个岗位`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "筛选失败");
    } finally {
      setLoading(false);
    }
  }

  async function onManualSubmit() {
    if (!manualTitle || !manualCompany) {
      setError("岗位名称和公司名称为必填");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await addManualJob({
        title: manualTitle,
        company: manualCompany,
        city: manualCity,
        salary: manualSalary,
        jd_text: manualJD,
      });
      setShowManual(false);
      setManualTitle("");
      setManualCompany("");
      setManualCity("");
      setManualSalary("");
      setManualJD("");
      await loadJobs();
      setStatus("手动录入成功");
    } catch (err) {
      setError(err instanceof Error ? err.message : "录入失败");
    } finally {
      setLoading(false);
    }
  }

  async function onDeleteJob(jobId: string, e: React.MouseEvent) {
    e.stopPropagation();
    setLoading(true);
    setError("");
    try {
      const result = await deleteJob(jobId);
      setStatus(`已删除，剩余 ${result.total} 个岗位`);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    } finally {
      setLoading(false);
    }
  }

  async function onEnrichDetails() {
    setLoading(true);
    setError("");
    setStatus("正在从详情页补充 JD，请稍候...");
    try {
      const result = await enrichJobDetails(10);
      setStatus(`已补充 ${result.enriched} 个岗位的 JD 描述`);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "JD 补充失败");
    } finally {
      setLoading(false);
    }
  }

  async function onClearAll() {
    setLoading(true);
    setError("");
    try {
      const result = await clearAllJobs();
      setStatus(`已清空 ${result.deleted} 个岗位`);
      setConfirmClear(false);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "清空失败");
    } finally {
      setLoading(false);
    }
  }

  const selectedJob = jobs.find((job) => job.id === selectedJobId);
  const selectedCount = selectedJobId ? 1 : 0;

  return (
    <section className="page-shell">
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">岗位池</p>
          <h2 className="page-title">捕获、筛选并选定当前目标岗位</h2>
          <p className="page-copy">
            岗位可从 Boss 直聘实时抓取，也可手动录入。点击岗位卡片查看完整 JD，选定后进入后续流程。
          </p>
        </div>
      </div>

      <div className="page-body">
        <div className="page-mainbar">
          {/* 工具栏 */}
          <div className="toolbar-strip">
            <div className="toolbar-group">
              <button
                type="button"
                className="button-primary"
                disabled={loading}
                onClick={() => setShowBoss(true)}
              >
                从 Boss 抓取
              </button>
              <button
                type="button"
                className="button-secondary"
                disabled={loading}
                onClick={onBossLogin}
              >
                登录 Boss 直聘
              </button>
              <button
                type="button"
                className="button-secondary"
                disabled={loading}
                onClick={() => setShowManual(true)}
              >
                + 手动录入
              </button>
              <button
                type="button"
                className="button-secondary"
                disabled={loading}
                onClick={onEnrichDetails}
              >
                补充 JD
              </button>
              <button
                type="button"
                className="button-secondary"
                disabled={loading}
                onClick={onCapture}
              >
                加载示例
              </button>
            </div>
            <div className="toolbar-group">
              {confirmClear ? (
                <>
                  <span className="text-warning">确认清空全部 {total} 个岗位？</span>
                  <button type="button" className="button-danger" disabled={loading} onClick={onClearAll}>
                    确认清空
                  </button>
                  <button type="button" className="button-secondary" onClick={() => setConfirmClear(false)}>
                    取消
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="button-secondary button-danger-outline"
                  disabled={loading || total === 0}
                  onClick={() => setConfirmClear(true)}
                >
                  清空全部
                </button>
              )}
            </div>
          </div>

          {/* Boss 抓取弹窗 */}
          {showBoss && (
            <div className="modal-overlay" onClick={() => setShowBoss(false)}>
              <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                  <h3 className="modal-title">从 Boss 直聘抓取</h3>
                  <button type="button" className="icon-button" onClick={() => setShowBoss(false)} aria-label="关闭">✕</button>
                </div>
                <div className="modal-body">
                  <div className="form-group">
                    <label className="form-label">搜索关键词</label>
                    <input className="form-input" value={bossKeyword} onChange={(e) => setBossKeyword(e.target.value)} placeholder="如 Python、前端" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">城市</label>
                    <select className="form-input" value={bossCity} onChange={(e) => setBossCity(e.target.value)}>
                      {["深圳", "北京", "上海", "广州", "杭州", "成都", "南京", "武汉", "西安", "苏州", "郑州", "长沙", "重庆", "天津", "合肥", "济南", "青岛", "厦门", "福州", "东莞", "佛山", "珠海", "大连", "昆明", "贵阳", "南宁", "南昌", "石家庄", "太原", "沈阳", "哈尔滨", "长春", "兰州", "海口", "无锡", "宁波", "温州"].map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">最多页数（每页 30 条）</label>
                    <select className="form-input" value={bossPages} onChange={(e) => setBossPages(e.target.value)}>
                      {[1, 2, 3, 5, 10].map((n) => (
                        <option key={n} value={n}>{n} 页</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="button-secondary" onClick={() => setShowBoss(false)}>取消</button>
                  <button type="button" className="button-primary" disabled={loading} onClick={onCaptureBoss}>
                    {loading ? "抓取中..." : "开始抓取"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 手动录入弹窗 */}
          {showManual && (
            <div className="modal-overlay" onClick={() => setShowManual(false)}>
              <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                  <h3 className="modal-title">手动录入岗位</h3>
                  <button type="button" className="icon-button" onClick={() => setShowManual(false)} aria-label="关闭">✕</button>
                </div>
                <div className="modal-body">
                  <div className="form-group">
                    <label className="form-label">岗位名称 *</label>
                    <input className="form-input" value={manualTitle} onChange={(e) => setManualTitle(e.target.value)} placeholder="如 Python 后端工程师" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">公司名称 *</label>
                    <input className="form-input" value={manualCompany} onChange={(e) => setManualCompany(e.target.value)} placeholder="如 A 科技有限公司" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">城市</label>
                    <input className="form-input" value={manualCity} onChange={(e) => setManualCity(e.target.value)} placeholder="如 深圳" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">薪资</label>
                    <input className="form-input" value={manualSalary} onChange={(e) => setManualSalary(e.target.value)} placeholder="如 20-30K" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">JD 描述</label>
                    <textarea className="form-input form-textarea" rows={4} value={manualJD} onChange={(e) => setManualJD(e.target.value)} placeholder="输入岗位 JD 描述..." />
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="button-secondary" onClick={() => setShowManual(false)}>取消</button>
                  <button type="button" className="button-primary" disabled={loading} onClick={onManualSubmit}>
                    {loading ? "提交中..." : "确认录入"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 筛选栏 */}
          <div className="toolbar-strip">
            <div className="toolbar-group">
              <input className="form-input form-input--inline" placeholder="按关键词筛选" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
              <input className="form-input form-input--inline" placeholder="按城市筛选" value={cityFilter} onChange={(e) => setCityFilter(e.target.value)} />
              <input className="form-input form-input--inline form-input--narrow" placeholder="薪资 ≥ K" value={minSalary} onChange={(e) => setMinSalary(e.target.value)} type="number" />
              <button type="button" className="button-primary" disabled={loading} onClick={onFilter}>筛选</button>
              <button type="button" className="button-secondary" disabled={loading} onClick={loadJobs}>重置</button>
            </div>
          </div>

          {error && <div className="banner banner-error">{error}</div>}

          {/* 岗位列表 */}
          <section className="page-section">
            <div className="page-section__top">
              <div>
                <div className="page-kicker">岗位列表</div>
                <p className="workspace-target-meta">
                  {loading ? "加载中..." : total > 0 ? `共 ${total} 条岗位` : "还没有岗位，请先抓取或录入。"}
                </p>
              </div>
            </div>

            {total > 0 ? (
              <div className="job-grid job-grid--compact">
                {jobs.map((job) => (
                  <article
                    key={job.id}
                    className={`job-card job-card--compact ${selectedJobId === job.id ? "job-card--selected" : ""}`}
                    onClick={() => setDetailJob(job)}
                    style={{ cursor: "pointer" }}
                  >
                    <div className="job-card__top">
                      <div className="stack">
                        <h3 className="job-card__title">{job.title}</h3>
                        <p className="job-card__meta">{job.company} · {job.city} · {job.salary}</p>
                      </div>
                      <div className="job-card__actions">
                        <button
                          type="button"
                          className="icon-button icon-button--sm"
                          onClick={(e) => onDeleteJob(job.id, e)}
                          aria-label={`删除 ${job.title}`}
                          title="删除此岗位"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                    <div className="job-tags">
                      {selectedJobId === job.id ? <span className="tag tag--active">当前已选中</span> : null}
                      <span className="tag tag--muted">
                        {job.source === "captured" ? "BOSS 抓取" : job.source === "manual" ? "手动录入" : job.source}
                      </span>
                      {job.keywords?.slice(0, 3).map((k: string) => (
                        <span key={k} className="tag">{k}</span>
                      ))}
                    </div>
                    <p className="job-card__body">{job.structured_summary || (job.jd_text ? job.jd_text.split("\n").filter(l => l.trim()).slice(0, 2).join(" · ") : "")}</p>
                    <div className="toolbar-row">
                      <button
                        type="button"
                        className={selectedJobId === job.id ? "button-secondary" : "button-primary"}
                        onClick={(e) => { e.stopPropagation(); onSelectJob(job); }}
                      >
                        {selectedJobId === job.id ? "已选为目标，点击切换" : "选为简历优化目标"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <strong>没有岗位</strong>
                <p>点击「从 Boss 抓取」搜索真实岗位，或点击「加载示例数据」快速体验。</p>
              </div>
            )}
          </section>
        </div>

        {/* 右侧信息栏 */}
        <aside className="workbench-rail" data-testid="job-summary-rail">
          <div className="metric-grid">
            <div className="metric-card">
              <span className="metric-card__label">结果</span>
              <span className="metric-card__value mono">{total}</span>
            </div>
            <div className="metric-card">
              <span className="metric-card__label">目标</span>
              <span className="metric-card__value mono">当前选中 {selectedCount} 个</span>
            </div>
            <div className="metric-card">
              <span className="metric-card__label">薪资</span>
              <span className="metric-card__value mono">{minSalary || "不限"}K+</span>
            </div>
          </div>
          <div className="panel panel-muted">
            <div className="panel-inner section-grid">
              <div><div className="page-kicker">当前条件</div></div>
              <div className="mini-list">
                <div className="mini-row"><span>关键词</span><strong>{keyword || "未设置"}</strong></div>
                <div className="mini-row"><span>城市</span><strong>{cityFilter || "不限"}</strong></div>
                <div className="mini-row"><span>状态</span><strong>{status || "未操作"}</strong></div>
              </div>
            </div>
          </div>
          <div className="panel panel-muted">
            <div className="panel-inner section-grid">
              <div><div className="page-kicker">当前目标</div>
                {selectedJob ? (
                  <div className="stack">
                    <h3 className="workspace-target-title">{selectedJob.title}</h3>
                    <p className="workspace-target-meta">{selectedJob.company} · {selectedJob.city} · {selectedJob.salary}</p>
                    <div className="job-tags">
                      {selectedJob.keywords?.slice(0, 4).map((k: string) => <span key={k} className="tag">{k}</span>)}
                    </div>
                  </div>
                ) : <p className="workspace-target-meta">还没有选中岗位。</p>}
              </div>
            </div>
          </div>
        </aside>
      </div>

      {/* JD 详情弹窗 */}
      {detailJob && <JobDetailModal job={detailJob} onClose={() => setDetailJob(null)} />}
    </section>
  );
}
