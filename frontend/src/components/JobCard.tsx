import type { KeyboardEvent } from "react";
import type { JobApplicationStatus, JobDecisionStatus, JobPosting } from "../lib/types";

type JobCardProps = {
  job: JobPosting;
  selected: boolean;
  expanded: boolean;
  customTags: string[];
  tagInput: string;
  filterTagList: string[];
  greeted: boolean;
  statusLabels: Record<JobApplicationStatus, string>;
  decisionLabels: Record<JobDecisionStatus, string>;
  onToggleSelected: () => void;
  onToggleDetail: () => void;
  onStatusChange: (status: JobApplicationStatus) => void;
  onDecisionChange: (status: JobDecisionStatus) => void;
  onRemoveCustomTag: (tag: string) => void;
  onTagInputChange: (value: string) => void;
  onAddCustomTag: () => void;
  onToggleKeywordTag: (tag: string) => void;
  onAddBlacklist: () => void;
  onDelete: () => void;
};

export function JobCard({
  job,
  selected,
  expanded,
  customTags,
  tagInput,
  filterTagList,
  greeted,
  statusLabels,
  decisionLabels,
  onToggleSelected,
  onToggleDetail,
  onStatusChange,
  onDecisionChange,
  onRemoveCustomTag,
  onTagInputChange,
  onAddCustomTag,
  onToggleKeywordTag,
  onAddBlacklist,
  onDelete,
}: JobCardProps) {
  function onTagKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") onAddCustomTag();
  }

  return (
    <li className={`job-card${selected ? " job-card--selected" : ""}`}>
      <div className="job-card__top">
        <div className="job-card-main">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelected}
            className="job-card-checkbox"
            aria-label={`选择岗位 ${job.title}`}
          />
          <div className="job-card-summary" onClick={onToggleDetail}>
            <h3 className="job-card__title">{job.title}</h3>
            <p className="job-card__meta">{job.company} · {job.city || "未知"} · {job.salary || "薪资面议"}</p>
            {job.fetched_at && (
              <p className="job-card__meta job-card__meta--sub">
                抓取: {new Date(job.fetched_at).toLocaleDateString("zh-CN")}
              </p>
            )}
          </div>
        </div>
        <div className="job-card-actions">
          {greeted && <span className="tag tag--green">已招呼</span>}
          {job.lifecycle_status === "suspected_expired" && <span className="tag tag--red" title={job.stale_reason || "岗位疑似过期"}>疑似过期</span>}
          <label className="job-status-control" title={job.application_note || "求职状态"}>
            <span>求职状态</span>
            <select
              aria-label="求职状态"
              className="form-input form-input--inline job-status-select"
              value={job.application_status || (greeted ? "greeted" : "pending")}
              onChange={e => onStatusChange(e.target.value as JobApplicationStatus)}
            >
              {Object.entries(statusLabels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label className={`job-status-control job-decision-control job-decision-control--${job.decision_status || "undecided"}`} title="岗位决策标签">
            <span>决策标签</span>
            <select
              aria-label="决策标签"
              className="form-input form-input--inline job-status-select job-decision-select"
              value={job.decision_status || "undecided"}
              onChange={e => onDecisionChange(e.target.value as JobDecisionStatus)}
            >
              {Object.entries(decisionLabels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          {customTags.map(tag => (
            <span key={tag} className="tag job-custom-tag" onClick={() => onRemoveCustomTag(tag)} title="点击删除标签">{tag} ×</span>
          ))}
          <input
            className="form-input form-input--inline job-tag-input"
            placeholder="加标签"
            value={tagInput}
            onChange={e => onTagInputChange(e.target.value)}
            onKeyDown={onTagKeyDown}
          />
          <button type="button" className="button-quiet" onClick={onToggleDetail}>
            {expanded ? "收起" : "JD"}
          </button>
          <button type="button" className="button-quiet button-danger" onClick={onAddBlacklist}>加入黑名单</button>
          <button type="button" className="button-quiet button-danger" onClick={onDelete}>删除</button>
        </div>
      </div>

      {job.keywords && job.keywords.length > 0 && (
        <div className="job-tags">
          {job.keywords.slice(0, 10).map(keyword => (
            <span
              key={keyword}
              className={`tag ${filterTagList.includes(keyword.toLowerCase()) ? "tag--active" : "tag--muted"}`}
              style={{ cursor: "pointer" }}
              onClick={() => onToggleKeywordTag(keyword)}
            >
              {keyword}
            </span>
          ))}
        </div>
      )}

      {expanded && (
        <div className="panel panel-muted" style={{ marginTop: 12 }}>
          <div className="panel-inner" style={{ padding: "14px 18px" }}>
            {job.jd_text && job.jd_text.length > 30 ? (
              <pre style={{ margin: 0, fontSize: 13, lineHeight: 1.75, whiteSpace: "pre-wrap", color: "var(--text-strong)" }}>{job.jd_text}</pre>
            ) : (
              <p className="text-muted" style={{ fontSize: 13 }}>暂无详细 JD，点击"获取JD详情"补充</p>
            )}
            {job.source_url && (
              <a href={job.source_url} target="_blank" rel="noopener noreferrer" className="job-source-link">
                在 BOSS 直聘查看
              </a>
            )}
          </div>
        </div>
      )}
    </li>
  );
}
