import { useState, useEffect, useMemo, useRef } from "react";
import { listJobPool, getJobPoolQuality, listBossCities, listBossFilterOptions, captureBossJobs, bossLogin, bossLoginStatus, enrichJdDetails, deleteJob, deleteBatchJobs, tagJob, clearAllJobs, listCompanyBlacklist, addCompanyBlacklist, deleteCompanyBlacklist, exportCompanyBlacklist, importCompanyBlacklist, cleanupExpiredJobs, keepExpiredJobs, mergeDuplicateJobs, updateJobApplicationStatus, updateJobDecisionStatus } from "../lib/api";
import type { BossCaptureFilters, BossFilterOptions, BossLoginStatus, CompanyBlacklistItem, JobApplicationStatus, JobDecisionStatus, JobPoolQuality, JobPosting } from "../lib/types";
import { HIDDEN_COMMON_TAGS_KEY, useWorkflowState, useWorkflowDispatch, actions } from "../lib/store";
import { EmptyState, ErrorBanner } from "../components/SharedUI";
import { CitySearchSelect } from "../components/CitySearchSelect";
import { JobFilterPanel } from "../components/JobFilterPanel";
import { JobCard } from "../components/JobCard";
import { CompanyBlacklistPanel } from "../components/CompanyBlacklistPanel";
import { buildCommonTags } from "../lib/jobTags";
import { formatApiError } from "../lib/workflowInsights";

const FALLBACK_CITY_OPTIONS = ["全国", "北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安", "郑州", "长沙", "苏州"];
const FILTER_LABELS: Array<[keyof BossCaptureFilters, string]> = [
  ["scale", "规模"],
  ["stage", "融资"],
  ["salary", "薪资"],
  ["experience", "经验"],
  ["degree", "学历"],
  ["industry", "行业"],
];
const APPLICATION_STATUS_LABELS: Record<JobApplicationStatus, string> = {
  pending: "待跟进",
  greeted: "已打招呼",
  applied: "已投递",
  interviewing: "面试中",
  rejected: "已拒绝",
  abandoned: "已放弃",
};
const DECISION_STATUS_LABELS: Record<JobDecisionStatus, string> = {
  undecided: "未决定",
  recommended: "推荐投递",
  watching: "观察",
  abandoned: "放弃",
  risky: "风险",
};
type QualityFilterKey = "" | "with_jd" | "missing_jd" | "suspected_expired" | "blacklisted" | "duplicates";

const QUALITY_FILTER_LABELS: Record<Exclude<QualityFilterKey, "">, string> = {
  with_jd: "已获取 JD",
  missing_jd: "缺少 JD",
  suspected_expired: "疑似过期",
  blacklisted: "黑名单命中",
  duplicates: "重复岗位",
};

export default function JobsPage({ onNavigate, visible = true }: { onNavigate: (page: string) => void; visible?: boolean }) {
  const { selectedJobIds } = useWorkflowState();
  const dispatch = useWorkflowDispatch();

  // ---- 抓取参数 ----
  const [keyword, setKeyword] = useState("产品经理");
  const [city, setCity] = useState("全国");
  const [cityOptions, setCityOptions] = useState<string[]>(FALLBACK_CITY_OPTIONS);
  const [maxPages, setMaxPages] = useState(3);
  const [captureFilters, setCaptureFilters] = useState<BossCaptureFilters>({});
  const [filterOptions, setFilterOptions] = useState<BossFilterOptions>({
    scale: [],
    stage: [],
    salary: [],
    experience: [],
    degree: [],
    industry: [],
  });

  // ---- 筛选参数 ----
  const [filterText, setFilterText] = useState("");
  const [filterCity, setFilterCity] = useState("");
  const [filterSalaryMin, setFilterSalaryMin] = useState("");
  const [filterSalaryMax, setFilterSalaryMax] = useState("");
  const [filterTags, setFilterTags] = useState("");
  const [filterApplicationStatus, setFilterApplicationStatus] = useState("");
  const [filterDecisionStatus, setFilterDecisionStatus] = useState("");
  const [qualityFilter, setQualityFilter] = useState<QualityFilterKey>("");

  // ---- 数据状态 ----
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);
  const [greetedStatus, setGreetedStatus] = useState<Record<string, boolean>>({});
  const [customTags, setCustomTags] = useState<Record<string, string[]>>({});
  const [tagInputs, setTagInputs] = useState<Record<string, string>>({});
  const [loggedIn, setLoggedIn] = useState(false);
  const [loginStatus, setLoginStatus] = useState<BossLoginStatus | null>(null);
  const [blacklist, setBlacklist] = useState<CompanyBlacklistItem[]>([]);
  const [blacklistInput, setBlacklistInput] = useState("");
  const [blacklistExpanded, setBlacklistExpanded] = useState(false);
  const [quality, setQuality] = useState<JobPoolQuality | null>(null);
  const [duplicatesExpanded, setDuplicatesExpanded] = useState(false);
  const blacklistImportRef = useRef<HTMLInputElement | null>(null);
  const [hiddenCommonTags, setHiddenCommonTags] = useState<string[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      const parsed = JSON.parse(window.localStorage.getItem(HIDDEN_COMMON_TAGS_KEY) || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    if (visible) {
      loadCityOptions();
      loadFilterOptions();
      loadBlacklist();
      loadJobs(qualityFilter === "blacklisted");
      loadQuality();
      // JD 抓取进行中不触发 checkStatus，防止抢占 Chrome 导致页面跳转
      if (!loading || loading !== "enrich") checkStatus();
    }
  }, [visible]);

  async function loadCityOptions() {
    try {
      const r = await listBossCities();
      const names = (r.cities || []).map(c => c.name).filter(Boolean);
      if (names.length > 0) setCityOptions(names);
    } catch (err) {
      console.warn("[jobs] 加载城市列表失败:", err);
    }
  }

  async function loadFilterOptions() {
    try {
      setFilterOptions(await listBossFilterOptions());
    } catch (err) {
      console.warn("[jobs] 加载抓取筛选项失败:", err);
    }
  }

  async function loadBlacklist() {
    try {
      const r = await listCompanyBlacklist();
      setBlacklist(r.companies || []);
    } catch (err) {
      console.warn("[jobs] 加载企业黑名单失败:", err);
    }
  }

  async function loadJobs(includeHidden = false) {
    try {
      const r = await listJobPool(includeHidden);
      const all: JobPosting[] = r.jobs || [];
      setJobs(all);
      const g: Record<string, boolean> = {};
      const t: Record<string, string[]> = {};
      all.forEach((j) => {
        if (j.greeted) g[j.id] = true;
        if (j.tags?.length) t[j.id] = j.tags.filter(tag => !tag.startsWith("@"));
      });
      setGreetedStatus(g);
      setCustomTags(t);
    } catch (err) {
      console.warn("[jobs] 加载岗位失败:", err);
    }
  }

  async function reloadJobsForQualityFilter(nextFilter: QualityFilterKey = qualityFilter) {
    await loadJobs(nextFilter === "blacklisted");
  }

  function applyQualityFilter(nextFilter: QualityFilterKey) {
    setQualityFilter(nextFilter);
    void reloadJobsForQualityFilter(nextFilter);
  }

  async function loadQuality() {
    try {
      setQuality(await getJobPoolQuality());
    } catch (err) {
      console.warn("[jobs] 加载岗位质量摘要失败:", err);
    }
  }

  async function checkStatus() {
    try { const r = await bossLoginStatus(); setLoggedIn(r.logged_in); setLoginStatus(r); }
    catch (err) { console.warn("[jobs] 检查登录状态失败:", err); }
  }

  async function onLogin() {
    setLoading("login"); setError("");
    try { const r = await bossLogin(); if (r.status === "ok") { setLoggedIn(true); await checkStatus(); } else setError(r.message || "登录失败"); }
    catch (err) { setError(err instanceof Error ? err.message : "登录失败"); }
    finally { setLoading(prev => prev === "login" ? "" : prev); }
  }

  async function onCapture() {
    setLoading("capture"); setError("");
    try {
      await captureBossJobs({
        keyword,
        city: city === "全国" ? "" : city,
        max_pages: maxPages,
        filters: captureFilters,
      });
      await reloadJobsForQualityFilter();
      await loadQuality();
    } catch (err) { setError(formatApiError(err) || "抓取失败"); }
    finally { setLoading(prev => prev === "capture" ? "" : prev); }
  }

  async function onEnrichJD() {
    setLoading("enrich"); setError("");
    try {
      await enrichJdDetails({ job_ids: selectedJobIds.length > 0 ? selectedJobIds : undefined, max_jobs: 30 });
      await reloadJobsForQualityFilter();
      await loadQuality();
    } catch (err) { setError(formatApiError(err) || "JD抓取失败"); }
    finally { setLoading(prev => prev === "enrich" ? "" : prev); }
  }

  async function addBlacklist(name: string) {
    const companyName = name.trim();
    if (!companyName) return;
    try {
      const r = await addCompanyBlacklist(companyName);
      setBlacklist(r.companies || []);
      setBlacklistInput("");
      await reloadJobsForQualityFilter();
      await loadQuality();
      if (r.removed > 0) setError(`已加入黑名单，并自动过滤 ${r.removed} 个岗位`);
    } catch (err) {
      setError(formatApiError(err) || "加入黑名单失败");
    }
  }

  async function removeBlacklist(name: string) {
    try {
      const r = await deleteCompanyBlacklist(name);
      setBlacklist(r.companies || []);
      if (qualityFilter === "blacklisted") {
        setQualityFilter("");
      }
      await loadJobs(false);
      await loadQuality();
      setError(r.restored ? `已移出黑名单，并恢复 ${r.restored} 个岗位` : "已移出黑名单");
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除黑名单失败");
    }
  }

  function downloadJson(filename: string, payload: unknown) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function onExportBlacklist() {
    try {
      const data = await exportCompanyBlacklist();
      downloadJson("company-blacklist.json", data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出黑名单失败");
    }
  }

  async function onImportBlacklist(file?: File) {
    if (!file) return;
    try {
      const payload = JSON.parse(await file.text());
      const r = await importCompanyBlacklist(payload);
      setBlacklist(r.companies || []);
      await reloadJobsForQualityFilter();
      await loadQuality();
      setError(`黑名单导入完成，共 ${r.total} 家，自动过滤 ${r.removed || 0} 个岗位`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导入黑名单失败");
    } finally {
      if (blacklistImportRef.current) blacklistImportRef.current.value = "";
    }
  }

  async function onCleanupExpired() {
    const ids = expiredJobs.map(j => j.id);
    if (ids.length === 0) return;
    if (!confirm(`确定清理 ${ids.length} 个疑似过期岗位？`)) return;
    try {
      await cleanupExpiredJobs(ids);
      dispatch(actions.setSelection(selectedJobIds.filter(id => !ids.includes(id))));
      await reloadJobsForQualityFilter();
      await loadQuality();
    } catch (err) {
      setError(err instanceof Error ? err.message : "清理过期岗位失败");
    }
  }

  async function onKeepExpired() {
    const ids = expiredJobs.map(j => j.id);
    if (ids.length === 0) return;
    try {
      await keepExpiredJobs(ids);
      await reloadJobsForQualityFilter();
      await loadQuality();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保留岗位失败");
    }
  }

  async function onMergeDuplicateGroup(jobIds: string[]) {
    if (jobIds.length < 2) return;
    if (!confirm(`确定合并这组 ${jobIds.length} 个重复岗位？系统会保留 JD 最完整的一条。`)) return;
    try {
      const r = await mergeDuplicateJobs(jobIds);
      dispatch(actions.setSelection(selectedJobIds.filter(id => !r.removed.includes(id))));
      await reloadJobsForQualityFilter();
      await loadQuality();
      setError(`重复岗位已合并，保留 ${r.kept}，删除 ${r.removed.length} 个`);
    } catch (err) {
      setError(formatApiError(err) || "合并重复岗位失败");
    }
  }

  async function onUpdateApplicationStatus(job: JobPosting, status: JobApplicationStatus) {
    try {
      await updateJobApplicationStatus(job.id, status, job.application_note || "");
      await reloadJobsForQualityFilter();
    } catch (err) {
      setError(formatApiError(err) || "更新求职状态失败");
    }
  }

  async function onUpdateDecisionStatus(job: JobPosting, status: JobDecisionStatus) {
    try {
      await updateJobDecisionStatus(job.id, status);
      await reloadJobsForQualityFilter();
    } catch (err) {
      setError(formatApiError(err) || "更新决策标签失败");
    }
  }

  function toggleJob(id: string) { dispatch(actions.toggleJobSelection(id)); }
  function selectAll() { dispatch(actions.selectAllJobs(filteredJobs.map(j => j.id))); }
  function clearSel() { dispatch(actions.clearSelection()); }

  async function onDeleteOne(id: string) {
    if (!confirm("确定删除该岗位？")) return;
    try {
      await deleteJob(id);
      if (selectedJobIds.includes(id)) toggleJob(id);
      if (detailId === id) setDetailId(null);
      await reloadJobsForQualityFilter();
      await loadQuality();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除岗位失败");
    }
  }

  async function onDeleteBatch() {
    if (selectedJobIds.length === 0) return;
    if (!confirm(`确定删除选中的 ${selectedJobIds.length} 个岗位？`)) return;
    try {
      await deleteBatchJobs(selectedJobIds);
      clearSel();
      setDetailId(null);
      await reloadJobsForQualityFilter();
      await loadQuality();
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量删除失败");
    }
  }

  async function onClearAll() {
    if (!confirm(`确定清空全部 ${jobs.length} 个岗位？此操作不可撤销。`)) return;
    try {
      await clearAllJobs();
      clearSel();
      setDetailId(null);
      await reloadJobsForQualityFilter();
      await loadQuality();
    } catch (err) {
      setError(err instanceof Error ? err.message : "清空岗位失败");
    }
  }

  async function addCustomTag(jobId: string, tag: string) {
    const cleanTag = tag.trim();
    if (!cleanTag) return;
    const current = customTags[jobId] || [];
    const newTags = current.includes(cleanTag) ? current : [...current, cleanTag];
    setCustomTags(prev => ({ ...prev, [jobId]: newTags }));
    setHiddenCommonTags(prev => {
      const next = prev.filter(t => t.toLowerCase() !== cleanTag.toLowerCase());
      if (typeof window !== "undefined") {
        window.localStorage.setItem(HIDDEN_COMMON_TAGS_KEY, JSON.stringify(next));
      }
      return next;
    });
    setTagInputs(prev => ({ ...prev, [jobId]: "" }));
    try {
      await tagJob(jobId, { tags: newTags });
    } catch (err) {
      setCustomTags(prev => ({ ...prev, [jobId]: current }));
      setTagInputs(prev => ({ ...prev, [jobId]: cleanTag }));
      setError(err instanceof Error ? err.message : "添加标签失败");
    }
  }

  function hideCommonTag(tag: string) {
    setHiddenCommonTags(prev => {
      const next = [...new Set([...prev, tag])];
      if (typeof window !== "undefined") {
        window.localStorage.setItem(HIDDEN_COMMON_TAGS_KEY, JSON.stringify(next));
      }
      return next;
    });
    setFilterTags(prev => filterTagList.includes(tag.toLowerCase())
      ? filterTagList.filter(t => t !== tag.toLowerCase()).join(", ")
      : prev);
  }

  function clearCommonTags() {
    setHiddenCommonTags(prev => {
      const next = [...new Set([...prev, ...allTags])];
      if (typeof window !== "undefined") {
        window.localStorage.setItem(HIDDEN_COMMON_TAGS_KEY, JSON.stringify(next));
      }
      return next;
    });
    setFilterTags("");
  }

  // ---- 多维度过滤 ----
  const filterTagList = useMemo(() => {
    return filterTags.split(/[,，\s]+/).map(t => t.trim().toLowerCase()).filter(Boolean);
  }, [filterTags]);

  const filteredJobs = useMemo(() => {
    const duplicateJobIds = new Set((quality?.duplicateGroups || []).flatMap(group => group.jobIds));
    return jobs.filter(j => {
      if (qualityFilter !== "blacklisted" && j.lifecycle_status === "blacklisted") return false;
      if (qualityFilter === "with_jd" && !(j.jd_text || "").trim()) return false;
      if (qualityFilter === "missing_jd" && (j.jd_text || "").trim()) return false;
      if (qualityFilter === "suspected_expired" && j.lifecycle_status !== "suspected_expired") return false;
      if (qualityFilter === "blacklisted" && j.lifecycle_status !== "blacklisted") return false;
      if (qualityFilter === "duplicates" && !duplicateJobIds.has(j.id)) return false;
      if (filterText) {
        const kw = filterText.toLowerCase();
        const matchTitle = j.title.toLowerCase().includes(kw);
        const matchCompany = j.company.toLowerCase().includes(kw);
        const matchTags = (j.keywords || []).some(k => k.toLowerCase().includes(kw));
        const matchJd = (j.jd_text || "").toLowerCase().includes(kw);
        const matchCustom = (customTags[j.id] || []).some(t => t.toLowerCase().includes(kw));
        if (!matchTitle && !matchCompany && !matchTags && !matchJd && !matchCustom) return false;
      }
      if (filterCity && (!j.city || !j.city.includes(filterCity))) return false;
      if (filterSalaryMin) {
        const min = parseInt(filterSalaryMin, 10);
        if (!isNaN(min) && (j.salary_min || 0) < min) return false;
      }
      if (filterSalaryMax) {
        const max = parseInt(filterSalaryMax, 10);
        if (!isNaN(max) && (j.salary_max || 0) > max) return false;
      }
      if (filterTagList.length > 0) {
        const jobTags = (j.keywords || []).map(k => k.toLowerCase());
        const myTags = (customTags[j.id] || []).map(t => t.toLowerCase());
        const allTags = [...jobTags, ...myTags];
        const hasTag = filterTagList.some(t => allTags.some(at => at.includes(t)));
        if (!hasTag) return false;
      }
      if (filterApplicationStatus) {
        const status = j.application_status || (j.greeted ? "greeted" : "pending");
        if (status !== filterApplicationStatus) return false;
      }
      if (filterDecisionStatus) {
        const status = j.decision_status || "undecided";
        if (status !== filterDecisionStatus) return false;
      }
      return true;
    });
  }, [jobs, quality, qualityFilter, filterText, filterCity, filterSalaryMin, filterSalaryMax, filterTagList, filterApplicationStatus, filterDecisionStatus, customTags]);

  const cities = useMemo(() => [...new Set(jobs.map(j => j.city).filter(Boolean))].sort(), [jobs]);
  const allTags = useMemo(() => buildCommonTags(jobs, hiddenCommonTags), [jobs, hiddenCommonTags]);
  const expiredJobs = useMemo(() => jobs.filter(j => j.lifecycle_status === "suspected_expired"), [jobs]);

  const selectedJobs = useMemo(() => jobs.filter(j => selectedJobIds.includes(j.id)), [jobs, selectedJobIds]);

  return (
    <section className="page-shell">
      {/* ── 页头 ── */}
      <div className="page-heading">
        <div className="stack">
          <p className="page-kicker">岗位抓取</p>
          <h2 className="page-title">BOSS 直聘岗位抓取与筛选</h2>
          <p className="page-copy">登录后抓取岗位，多维度筛选，获取JD详情后进入尽调。</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span className={selectedJobIds.length > 0 ? "tag tag--active" : "tag"}>{selectedJobIds.length} 个已选</span>
          {selectedJobIds.length > 0 && (
            <button type="button" className="button-primary" onClick={() => onNavigate("diligence")}>开始尽调 →</button>
          )}
        </div>
      </div>

      {/* ── 错误 ── */}
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {/* ── 已选岗位图集 ── */}
      {selectedJobs.length > 0 && (
        <div className="panel panel-strong">
          <div className="panel-inner">
            <div className="page-section__top" style={{ marginBottom: selectedJobs.length > 0 ? 10 : 0 }}>
              <div className="page-kicker" style={{ marginBottom: 0 }}>当前已选 ({selectedJobs.length})</div>
              <button type="button" className="button-quiet" onClick={clearSel}>清空选择</button>
            </div>
            <div className="selected-mini-bar">
              {selectedJobs.map(j => (
                <div key={j.id} className="selected-mini-card" onClick={() => toggleJob(j.id)} title="点击取消选择">
                  <span style={{ fontSize: 15, lineHeight: 1 }}>×</span>
                  <span>{j.title}</span>
                  <span style={{ color: "var(--text-muted)", fontSize: 10 }}>{j.company}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── 抓取控制 ── */}
      <div className="panel panel-strong">
        <div className="panel-inner">
          <div className="capture-panel-top">
            <div>
              <div className="page-kicker" style={{ marginBottom: 4 }}>抓取控制</div>
              <p className="capture-panel-copy">先确认 BOSS 登录状态，再设置岗位条件并开始抓取。</p>
            </div>
            <span className={loggedIn ? "tag tag--green" : "tag tag--red"}>
              {loggedIn ? "已登录" : "未登录"}
            </span>
          </div>

          <div className="login-status-strip">
            <div className="login-status-main">
              <span className={loggedIn ? "login-dot login-dot--ok" : "login-dot login-dot--warn"} />
              <p className="login-status-copy">
                {loginStatus
                  ? `${loginStatus.message}${loginStatus.action ? ` · ${loginStatus.action}` : ""}`
                  : "尚未检测登录状态"}
              </p>
            </div>
            <div className="login-status-actions">
              {!loggedIn && (
                <button type="button" className="button-primary" disabled={loading === "login"} onClick={onLogin}>
                  {loading === "login" ? "登录中..." : "登录 BOSS"}
                </button>
              )}
              <button type="button" className="button-secondary" disabled={loading === "login"} onClick={checkStatus}>
                重新检测
              </button>
            </div>
          </div>

          <div className="capture-grid">
            <div className="field">
              <label className="field-label">岗位关键词</label>
              <input className="form-input form-input--inline" value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="如: 产品经理" />
            </div>
            <div className="field">
              <label className="field-label">城市</label>
              <CitySearchSelect value={city} options={cityOptions} onChange={setCity} />
            </div>
            <div className="field">
              <label className="field-label">页数</label>
              <select className="form-input form-input--inline" value={maxPages} onChange={e => setMaxPages(Number(e.target.value))}>
                {[1,2,3,5,8,10].map(n => <option key={n} value={n}>{n} 页</option>)}
              </select>
            </div>
            <div className="capture-actions">
              <button type="button" className="button-primary" disabled={loading === "capture"} onClick={onCapture}>
                {loading === "capture" ? "抓取中..." : "开始抓取"}
              </button>
              <button type="button" className="button-secondary" disabled={loading === "enrich"} onClick={onEnrichJD}>
                {loading === "enrich" ? "获取中..." : "获取 JD 详情"}
              </button>
            </div>
          </div>

          <div className="capture-filter-grid" aria-label="高级筛选">
            {FILTER_LABELS.map(([key, label]) => (
              <div key={key} className="field">
                <label className="field-label">{label}</label>
                <select
                  className="form-input form-input--inline"
                  value={captureFilters[key] || ""}
                  onChange={e => setCaptureFilters(prev => ({ ...prev, [key]: e.target.value || undefined }))}
                >
                  <option value="">不限</option>
                  {(filterOptions[key] || []).filter(opt => opt.value !== "0").map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          <CompanyBlacklistPanel
            companies={blacklist}
            inputValue={blacklistInput}
            expanded={blacklistExpanded}
            importInputRef={blacklistImportRef}
            onInputChange={setBlacklistInput}
            onAdd={addBlacklist}
            onRemove={removeBlacklist}
            onToggleExpanded={() => setBlacklistExpanded(prev => !prev)}
            onExport={onExportBlacklist}
            onImport={onImportBlacklist}
          />
        </div>
      </div>

      {quality && (
        <div className="panel panel-strong">
          <div className="panel-inner">
            <div className="page-section__top" style={{ marginBottom: 12 }}>
              <div>
                <div className="page-kicker" style={{ marginBottom: 4 }}>岗位池质量</div>
                <p className="capture-panel-copy">点击卡片可直接筛出对应岗位，用于定位缺失 JD、重复、过期等数据问题。</p>
              </div>
              <div className="toolbar-strip">
                {qualityFilter && (
                  <span className="tag tag--active">
                    当前筛选: {QUALITY_FILTER_LABELS[qualityFilter]}
                  </span>
                )}
                {qualityFilter && (
                  <button type="button" className="button-quiet" onClick={() => applyQualityFilter("")}>清除质量筛选</button>
                )}
                {quality.duplicateGroups.length > 0 && (
                  <button type="button" className="button-secondary" onClick={() => setDuplicatesExpanded(prev => !prev)}>
                    {duplicatesExpanded ? "收起重复组" : `查看重复组 ${quality.duplicateGroups.length}`}
                  </button>
                )}
              </div>
            </div>
            <div className="quality-metric-grid">
              <button type="button" className={`quality-metric ${qualityFilter === "" ? "quality-metric--active" : ""}`} onClick={() => applyQualityFilter("")}>
                <span>总岗位</span><strong>{quality.summary.total}</strong>
              </button>
              <button type="button" className={`quality-metric ${qualityFilter === "with_jd" ? "quality-metric--active" : ""}`} onClick={() => applyQualityFilter("with_jd")}>
                <span>已获取 JD</span><strong>{quality.summary.with_jd}</strong>
              </button>
              <button type="button" className={`quality-metric ${qualityFilter === "missing_jd" ? "quality-metric--active" : ""}`} onClick={() => applyQualityFilter("missing_jd")}>
                <span>缺少 JD</span><strong>{quality.summary.missing_jd}</strong>
              </button>
              <button type="button" className={`quality-metric ${qualityFilter === "suspected_expired" ? "quality-metric--active" : ""}`} onClick={() => applyQualityFilter("suspected_expired")}>
                <span>疑似过期</span><strong>{quality.summary.suspected_expired}</strong>
              </button>
              <button type="button" className={`quality-metric ${qualityFilter === "blacklisted" ? "quality-metric--active" : ""}`} onClick={() => applyQualityFilter("blacklisted")}>
                <span>黑名单命中</span><strong>{quality.summary.blacklisted}</strong>
              </button>
              <button type="button" className={`quality-metric ${qualityFilter === "duplicates" ? "quality-metric--active" : ""}`} onClick={() => applyQualityFilter("duplicates")}>
                <span>重复岗位</span><strong>{quality.summary.duplicate_jobs}</strong>
              </button>
            </div>
            <div className="application-board">
              {(Object.keys(APPLICATION_STATUS_LABELS) as JobApplicationStatus[]).map(status => (
                <button
                  key={status}
                  type="button"
                  className={`application-board__item ${filterApplicationStatus === status ? "application-board__item--active" : ""}`}
                  onClick={() => setFilterApplicationStatus(filterApplicationStatus === status ? "" : status)}
                >
                  <span>{APPLICATION_STATUS_LABELS[status]}</span>
                  <strong>{quality.summary.application_statuses?.[status] || 0}</strong>
                </button>
              ))}
            </div>
            {duplicatesExpanded && quality.duplicateGroups.length > 0 && (
              <div className="duplicate-group-list">
                {quality.duplicateGroups.slice(0, 8).map(group => (
                  <div key={group.key} className="duplicate-group-item">
                    <div>
                      <strong>{group.company} · {group.title}</strong>
                      <p>{group.city || "未知城市"} · {group.count} 个重复 · {group.withJd} 个已有 JD</p>
                    </div>
                    <button type="button" className="button-quiet" onClick={() => dispatch(actions.setSelection(group.jobIds))}>
                      选中这组
                    </button>
                    <button type="button" className="button-secondary button-secondary--sm" onClick={() => onMergeDuplicateGroup(group.jobIds)}>
                      合并这组
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {expiredJobs.length > 0 && (
        <div className="panel panel-strong">
          <div className="panel-inner">
            <div className="toolbar-strip">
              <span className="tag tag--red">疑似过期 {expiredJobs.length} 个</span>
              <span className="text-muted" style={{ fontSize: 12 }}>这些岗位抓取时间超过 90 天，建议重新确认后再进入尽调。</span>
              <button type="button" className="button-secondary" onClick={onKeepExpired}>本次保留</button>
              <button type="button" className="button-quiet button-danger" onClick={onCleanupExpired}>清理疑似过期</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 筛选工具栏 ── */}
      {jobs.length > 0 && (
        <JobFilterPanel
          totalJobs={jobs.length}
          filteredJobs={filteredJobs.length}
          filterText={filterText}
          filterCity={filterCity}
          filterSalaryMin={filterSalaryMin}
          filterSalaryMax={filterSalaryMax}
          filterTags={filterTags}
          filterApplicationStatus={filterApplicationStatus}
          filterDecisionStatus={filterDecisionStatus}
          cities={cities}
          commonTags={allTags}
          filterTagList={filterTagList}
          statusLabels={APPLICATION_STATUS_LABELS}
          decisionLabels={DECISION_STATUS_LABELS}
          selectedCount={selectedJobIds.length}
          onFilterTextChange={setFilterText}
          onFilterCityChange={setFilterCity}
          onFilterSalaryMinChange={setFilterSalaryMin}
          onFilterSalaryMaxChange={setFilterSalaryMax}
          onFilterTagsChange={setFilterTags}
          onFilterApplicationStatusChange={setFilterApplicationStatus}
          onFilterDecisionStatusChange={setFilterDecisionStatus}
          onHideCommonTag={hideCommonTag}
          onClearCommonTags={clearCommonTags}
          onSelectAllTags={() => setFilterTags(allTags.map(t => t.toLowerCase()).join(", "))}
          onSelectAll={selectAll}
          onClearSelection={clearSel}
          onDeleteSelected={onDeleteBatch}
          onClearAllJobs={onClearAll}
        />
      )}

      {/* ── 岗位列表 ── */}
      {jobs.length === 0 ? (
        <div className="panel panel-strong">
          <div className="panel-inner">
            <EmptyState icon="💼" title="暂无岗位数据" desc="登录 BOSS 直聘后输入关键词和城市，点击「开始抓取」获取岗位。" />
          </div>
        </div>
      ) : (
        <ul className="list-reset job-grid">
          {filteredJobs.map(job => {
            const sel = selectedJobIds.includes(job.id);
            const showDetail = detailId === job.id;
            const tags = customTags[job.id] || [];
            return (
              <JobCard
                key={job.id}
                job={job}
                selected={sel}
                expanded={showDetail}
                customTags={tags}
                tagInput={tagInputs[job.id] || ""}
                filterTagList={filterTagList}
                greeted={Boolean(greetedStatus[job.id])}
                statusLabels={APPLICATION_STATUS_LABELS}
                decisionLabels={DECISION_STATUS_LABELS}
                onToggleSelected={() => toggleJob(job.id)}
                onToggleDetail={() => setDetailId(showDetail ? null : job.id)}
                onStatusChange={(status) => onUpdateApplicationStatus(job, status)}
                onDecisionChange={(status) => onUpdateDecisionStatus(job, status)}
                onRemoveCustomTag={(tag) => {
                  const newTags = tags.filter(x => x !== tag);
                  setCustomTags(prev => ({ ...prev, [job.id]: newTags }));
                  tagJob(job.id, { tags: newTags }).catch((e: unknown) => {
                    setCustomTags(prev => ({ ...prev, [job.id]: tags }));
                    setError(e instanceof Error ? e.message : "删除标签失败");
                  });
                }}
                onTagInputChange={(value) => setTagInputs(prev => ({ ...prev, [job.id]: value }))}
                onAddCustomTag={() => addCustomTag(job.id, tagInputs[job.id] || "")}
                onToggleKeywordTag={(keyword) => {
                  const current = filterTagList;
                  setFilterTags(current.includes(keyword.toLowerCase())
                    ? current.filter(x => x !== keyword.toLowerCase()).join(", ")
                    : [...current, keyword.toLowerCase()].join(", "));
                }}
                onAddBlacklist={() => addBlacklist(job.company)}
                onDelete={() => onDeleteOne(job.id)}
              />
            );
          })}
        </ul>
      )}
    </section>
  );
}
