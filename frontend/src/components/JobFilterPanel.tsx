import type { JobApplicationStatus, JobDecisionStatus } from "../lib/types";

type JobFilterPanelProps = {
  totalJobs: number;
  filteredJobs: number;
  filterText: string;
  filterCity: string;
  filterSalaryMin: string;
  filterSalaryMax: string;
  filterTags: string;
  filterApplicationStatus: string;
  filterDecisionStatus: string;
  cities: string[];
  commonTags: string[];
  filterTagList: string[];
  statusLabels: Record<JobApplicationStatus, string>;
  decisionLabels: Record<JobDecisionStatus, string>;
  selectedCount: number;
  onFilterTextChange: (value: string) => void;
  onFilterCityChange: (value: string) => void;
  onFilterSalaryMinChange: (value: string) => void;
  onFilterSalaryMaxChange: (value: string) => void;
  onFilterTagsChange: (value: string) => void;
  onFilterApplicationStatusChange: (value: string) => void;
  onFilterDecisionStatusChange: (value: string) => void;
  onHideCommonTag: (tag: string) => void;
  onClearCommonTags: () => void;
  onSelectAllTags: () => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onDeleteSelected: () => void;
  onClearAllJobs: () => void;
};

export function JobFilterPanel({
  totalJobs,
  filteredJobs,
  filterText,
  filterCity,
  filterSalaryMin,
  filterSalaryMax,
  filterTags,
  filterApplicationStatus,
  filterDecisionStatus,
  cities,
  commonTags,
  filterTagList,
  statusLabels,
  decisionLabels,
  selectedCount,
  onFilterTextChange,
  onFilterCityChange,
  onFilterSalaryMinChange,
  onFilterSalaryMaxChange,
  onFilterTagsChange,
  onFilterApplicationStatusChange,
  onFilterDecisionStatusChange,
  onHideCommonTag,
  onClearCommonTags,
  onSelectAllTags,
  onSelectAll,
  onClearSelection,
  onDeleteSelected,
  onClearAllJobs,
}: JobFilterPanelProps) {
  function toggleTag(tag: string) {
    const key = tag.toLowerCase();
    const next = filterTagList.includes(key)
      ? filterTagList.filter(item => item !== key).join(", ")
      : [...filterTagList, key].join(", ");
    onFilterTagsChange(next);
  }

  return (
    <div className="panel panel-strong">
      <div className="panel-inner">
        <div className="page-kicker" style={{ marginBottom: 10 }}>筛选 ({filteredJobs}/{totalJobs})</div>
        <div className="job-filter-grid">
          <div className="field job-filter-field job-filter-field--keyword">
            <label className="field-label" htmlFor="job-filter-keyword">关键词搜索</label>
            <input id="job-filter-keyword" className="form-input" value={filterText} onChange={e => onFilterTextChange(e.target.value)} placeholder="岗位/公司/技能..." />
          </div>
          <div className="field job-filter-field job-filter-field--city">
            <label className="field-label" htmlFor="job-filter-city">城市</label>
            <select id="job-filter-city" className="form-input" value={filterCity} onChange={e => onFilterCityChange(e.target.value)}>
              <option value="">全部</option>
              {cities.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="field job-filter-field job-filter-field--salary">
            <label className="field-label" htmlFor="job-filter-salary-min">最低薪资(K)</label>
            <input id="job-filter-salary-min" className="form-input" type="number" value={filterSalaryMin} onChange={e => onFilterSalaryMinChange(e.target.value)} placeholder="不限" min={0} />
          </div>
          <div className="field job-filter-field job-filter-field--salary">
            <label className="field-label" htmlFor="job-filter-salary-max">最高薪资(K)</label>
            <input id="job-filter-salary-max" className="form-input" type="number" value={filterSalaryMax} onChange={e => onFilterSalaryMaxChange(e.target.value)} placeholder="不限" min={0} />
          </div>
          <div className="field job-filter-field job-filter-field--tags">
            <label className="field-label" htmlFor="job-filter-tags">标签筛选</label>
            <input id="job-filter-tags" className="form-input" value={filterTags} onChange={e => onFilterTagsChange(e.target.value)} placeholder="如: Python, 远程, AI" />
          </div>
          <div className="field job-filter-field job-filter-field--status">
            <label className="field-label" htmlFor="job-filter-status">求职状态</label>
            <select id="job-filter-status" className="form-input" value={filterApplicationStatus} onChange={e => onFilterApplicationStatusChange(e.target.value)}>
              <option value="">全部</option>
              {(Object.keys(statusLabels) as JobApplicationStatus[]).map(status => (
                <option key={status} value={status}>{statusLabels[status]}</option>
              ))}
            </select>
          </div>
          <div className="field job-filter-field job-filter-field--decision">
            <label className="field-label" htmlFor="job-filter-decision">决策标签</label>
            <select id="job-filter-decision" className="form-input" value={filterDecisionStatus} onChange={e => onFilterDecisionStatusChange(e.target.value)}>
              <option value="">全部</option>
              {(Object.keys(decisionLabels) as JobDecisionStatus[]).map(status => (
                <option key={status} value={status}>{decisionLabels[status]}</option>
              ))}
            </select>
          </div>
          <div className="field filter-tags-field">
            <label className="field-label">常用标签</label>
            <div className="filter-tags">
              {commonTags.slice(0, 12).map(tag => (
                <span key={tag} className={`tag filter-tag ${filterTagList.includes(tag.toLowerCase()) ? "tag--active" : "tag--muted"}`} onClick={() => toggleTag(tag)}>
                  <span>{tag}</span>
                  <button type="button" className="tag-remove-button" aria-label={`从常用标签删除 ${tag}`} title="从常用标签删除" onClick={(e) => { e.stopPropagation(); onHideCommonTag(tag); }}>×</button>
                </span>
              ))}
              {filterTagList.length > 0 && (
                <span className="tag tag--red filter-tag" onClick={() => onFilterTagsChange("")}>清空筛选</span>
              )}
              {filterApplicationStatus && (
                <span className="tag tag--red filter-tag" onClick={() => onFilterApplicationStatusChange("")}>清空状态</span>
              )}
              {filterDecisionStatus && (
                <span className="tag tag--red filter-tag" onClick={() => onFilterDecisionStatusChange("")}>清空决策</span>
              )}
              {commonTags.length > 0 && (
                <span className="tag filter-tag filter-tag--secondary" onClick={onSelectAllTags}>全选标签</span>
              )}
              {commonTags.length > 0 && (
                <button type="button" className="button-quiet button-danger" onClick={onClearCommonTags}>清空常用</button>
              )}
            </div>
          </div>
        </div>
        <div className="toolbar-strip jobs-bulk-actions">
          <button type="button" className="button-quiet" onClick={onSelectAll}>全选</button>
          <button type="button" className="button-quiet" onClick={onClearSelection}>取消全选</button>
          {selectedCount > 0 && (
            <button type="button" className="button-quiet button-danger" onClick={onDeleteSelected}>删除选中 ({selectedCount})</button>
          )}
          {totalJobs > 0 && (
            <button type="button" className="button-quiet button-danger" onClick={onClearAllJobs}>清空全部</button>
          )}
        </div>
      </div>
    </div>
  );
}
