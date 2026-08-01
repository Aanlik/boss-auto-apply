// ============================================================
// 全局状态管理 — React Context + useReducer
// 替代 App.tsx 中的 props drilling，所有页面可直接消费
// ============================================================

import { createContext, useContext, useReducer, useEffect, type Dispatch, type ReactNode } from "react";
import type {
  WorkflowState, ResumeProfile, UploadedFile,
  DiligenceReport, RankingResult,
  JDAnalysis, ResumeOptimizationResult
} from "./types";

// ── 持久化 key + schema 版本 ──
export const STORAGE_KEY = "boss-workbench-state-v4";
export const ACTIVE_PAGE_KEY = "boss-workbench-active-page";
export const HIDDEN_COMMON_TAGS_KEY = "boss-workbench-hidden-common-tags";
const SCHEMA_VERSION = 4;

// ── 空状态 ──
function createEmptyState(): WorkflowState {
  return {
    selectedJobIds: [],
    greetingJobIds: [],
    resumeProfile: null,
    uploadedFiles: [],
    diligenceReports: {},
    rankingResults: [],
    jdAnalyses: {},
    optimizations: {},
    greetingTexts: {},
    chatMessages: {},
  };
}

function loadState(): WorkflowState {
  if (typeof window === "undefined") return createEmptyState();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return createEmptyState();
    const parsed = JSON.parse(raw) as Record<string, unknown> & Partial<WorkflowState>;

    // 版本校验：schema 不兼容则丢弃旧数据
    if (parsed._schemaVersion !== SCHEMA_VERSION) {
      console.warn(`[store] Schema 版本不匹配 (本地: ${parsed._schemaVersion}, 当前: ${SCHEMA_VERSION})，重置状态`);
      window.localStorage.removeItem(STORAGE_KEY);
      return createEmptyState();
    }
    return {
      selectedJobIds: Array.isArray(parsed.selectedJobIds) ? parsed.selectedJobIds : [],
      greetingJobIds: Array.isArray(parsed.greetingJobIds) ? parsed.greetingJobIds : [],
      resumeProfile: parsed.resumeProfile || null,
      uploadedFiles: Array.isArray(parsed.uploadedFiles) ? parsed.uploadedFiles : [],
      diligenceReports: parsed.diligenceReports || {},
      rankingResults: Array.isArray(parsed.rankingResults) ? parsed.rankingResults : [],
      jdAnalyses: parsed.jdAnalyses || {},
      optimizations: parsed.optimizations || {},
      greetingTexts: parsed.greetingTexts || {},
      chatMessages: parsed.chatMessages || {},
    };
  } catch (e) {
    console.warn("[store] 加载状态失败:", e);
    return createEmptyState();
  }
}

function persist(state: WorkflowState) {
  if (typeof window === "undefined") return;
  const payload = { ...compactForStorage(state), _schemaVersion: SCHEMA_VERSION };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (e) {
    console.warn("[store] 持久化失败（可能数据过大）:", e);
    // 降级：仅保存核心字段
    try {
      const minimal = { resumeProfile: state.resumeProfile, uploadedFiles: state.uploadedFiles, selectedJobIds: state.selectedJobIds, _schemaVersion: SCHEMA_VERSION };
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(minimal));
    } catch {}
  }
}

function compactForStorage(state: WorkflowState): WorkflowState {
  const reports = Object.fromEntries(Object.entries(state.diligenceReports).map(([key, report]) => {
    const businessInfo = report.businessInfo
      ? {
          ...report.businessInfo,
          apiEntries: undefined,
          raw: undefined,
        }
      : report.businessInfo;
    return [key, { ...report, businessInfo }];
  }));
  return { ...state, diligenceReports: reports };
}

export function clearLocalWorkflowStorage() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.localStorage.removeItem(ACTIVE_PAGE_KEY);
  window.localStorage.removeItem(HIDDEN_COMMON_TAGS_KEY);
  for (const key of Object.keys(window.localStorage)) {
    if (key.startsWith("chat-")) {
      window.localStorage.removeItem(key);
    }
  }
}

// ── Actions ──
type Action =
  | { type: "SET_RESUME_PROFILE"; profile: ResumeProfile | null }
  | { type: "SET_UPLOADED_FILES"; files: UploadedFile[] }
  | { type: "TOGGLE_JOB_SELECTION"; jobId: string }
  | { type: "SELECT_ALL_JOBS"; jobIds: string[] }
  | { type: "CLEAR_SELECTION" }
  | { type: "SET_SELECTION"; jobIds: string[] }
  | { type: "SET_GREETING_SELECTION"; jobIds: string[] }
  | { type: "SET_DILIGENCE_REPORTS"; reports: Record<string, DiligenceReport> }
  | { type: "SET_RANKING_RESULTS"; results: RankingResult[] }
  | { type: "SET_JD_ANALYSES"; analyses: Record<string, JDAnalysis> }
  | { type: "SET_OPTIMIZATIONS"; opts: Record<string, ResumeOptimizationResult> }
  | { type: "SET_GREETING_TEXTS"; texts: Record<string, string> }
  | { type: "SET_CHAT_MESSAGES"; msgs: Record<string, Array<{role:string;content:string}>> }
  | { type: "MERGE_CHAT_MESSAGE"; key: string; messages: Array<{role:string;content:string}> | null }
  | { type: "HYDRATE_FROM_BACKEND"; payload: BackendHydrationPayload };

function reducer(state: WorkflowState, action: Action): WorkflowState {
  switch (action.type) {
    case "SET_RESUME_PROFILE":
      return { ...state, resumeProfile: action.profile };
    case "SET_UPLOADED_FILES":
      return { ...state, uploadedFiles: action.files };
    case "TOGGLE_JOB_SELECTION":
      return {
        ...state,
        selectedJobIds: state.selectedJobIds.includes(action.jobId)
          ? state.selectedJobIds.filter(id => id !== action.jobId)
          : [...state.selectedJobIds, action.jobId],
      };
    case "SELECT_ALL_JOBS":
      return { ...state, selectedJobIds: [...new Set([...state.selectedJobIds, ...action.jobIds])] };
    case "CLEAR_SELECTION":
      return { ...state, selectedJobIds: [] };
    case "SET_SELECTION":
      return { ...state, selectedJobIds: action.jobIds };
    case "SET_GREETING_SELECTION":
      return { ...state, greetingJobIds: action.jobIds };
    case "SET_DILIGENCE_REPORTS":
      return { ...state, diligenceReports: action.reports };
    case "SET_RANKING_RESULTS":
      return { ...state, rankingResults: action.results };
    case "SET_JD_ANALYSES":
      return { ...state, jdAnalyses: action.analyses };
    case "SET_OPTIMIZATIONS":
      return { ...state, optimizations: action.opts };
    case "SET_GREETING_TEXTS":
      return { ...state, greetingTexts: action.texts };
    case "SET_CHAT_MESSAGES":
      return { ...state, chatMessages: action.msgs };
    case "MERGE_CHAT_MESSAGE":
      if (action.messages === null) {
        const { [action.key]: _, ...rest } = state.chatMessages;
        return { ...state, chatMessages: rest };
      }
      return { ...state, chatMessages: { ...state.chatMessages, [action.key]: action.messages } };
    case "HYDRATE_FROM_BACKEND":
      return hydrateWorkflowStateFromBackend(state, action.payload);
    default:
      return state;
  }
}

type BackendHydrationPayload = {
  selection?: { selectedJobIds?: unknown };
  greetingSelection?: { greetingJobIds?: unknown };
  activeResume?: { profile?: unknown };
  files?: { files?: unknown };
  jobs?: { jobs?: unknown };
  diligence?: { reports?: unknown };
  rankings?: { rankings?: unknown };
  greetings?: { greetings?: unknown };
  optimizations?: { optimizations?: unknown };
  chats?: { chats?: unknown };
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export function hydrateWorkflowStateFromBackend(state: WorkflowState, payload: BackendHydrationPayload): WorkflowState {
  const jobs = Array.isArray(payload.jobs?.jobs) ? payload.jobs.jobs : [];
  const savedGreetingJobIds = Array.isArray(payload.greetingSelection?.greetingJobIds)
    ? payload.greetingSelection.greetingJobIds.map(String)
    : null;
  const savedJdAnalyses = Object.fromEntries(
    jobs
      .filter((job): job is Record<string, unknown> => isRecord(job) && Boolean(job.id) && isRecord(job.jd_analysis))
      .map(job => [String(job.id), job.jd_analysis]),
  ) as WorkflowState["jdAnalyses"];

  return {
    ...state,
    selectedJobIds: Array.isArray(payload.selection?.selectedJobIds)
      ? payload.selection.selectedJobIds.map(String)
      : state.selectedJobIds,
    // 后端已持久化时以其为准，避免过期的浏览器缓存重新带回旧的打招呼批次。
    greetingJobIds: savedGreetingJobIds ?? state.greetingJobIds,
    resumeProfile: isRecord(payload.activeResume?.profile)
      ? payload.activeResume.profile as WorkflowState["resumeProfile"]
      : state.resumeProfile,
    uploadedFiles: Array.isArray(payload.files?.files)
      ? payload.files.files as WorkflowState["uploadedFiles"]
      : state.uploadedFiles,
    diligenceReports: isRecord(payload.diligence?.reports)
      ? payload.diligence.reports as WorkflowState["diligenceReports"]
      : state.diligenceReports,
    rankingResults: Array.isArray(payload.rankings?.rankings)
      ? payload.rankings.rankings as WorkflowState["rankingResults"]
      : state.rankingResults,
    jdAnalyses: { ...savedJdAnalyses, ...state.jdAnalyses },
    optimizations: isRecord(payload.optimizations?.optimizations)
      ? { ...state.optimizations, ...payload.optimizations.optimizations } as WorkflowState["optimizations"]
      : state.optimizations,
    greetingTexts: isRecord(payload.greetings?.greetings)
      ? payload.greetings.greetings as WorkflowState["greetingTexts"]
      : state.greetingTexts,
    chatMessages: isRecord(payload.chats?.chats)
      ? { ...state.chatMessages, ...payload.chats.chats } as WorkflowState["chatMessages"]
      : state.chatMessages,
  };
}

// ── Context ──
const StateCtx = createContext<WorkflowState>(createEmptyState());
const DispatchCtx = createContext<Dispatch<Action>>(() => {});

// ── 后端 selection 同步 ──
let _selectionSyncReady = false;
let _selectionSyncTimer: ReturnType<typeof setTimeout> | null = null;
let _greetingSelectionSyncTimer: ReturnType<typeof setTimeout> | null = null;

function syncSelectionToBackend(ids: string[]) {
  if (!_selectionSyncReady) return;
  if (_selectionSyncTimer) clearTimeout(_selectionSyncTimer);
  _selectionSyncTimer = setTimeout(() => {
    fetch("/api/workflow/selection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selectedJobIds: ids }),
    }).catch(() => {});
  }, 500);
}

function syncGreetingSelectionToBackend(ids: string[]) {
  if (!_selectionSyncReady) return;
  if (_greetingSelectionSyncTimer) clearTimeout(_greetingSelectionSyncTimer);
  _greetingSelectionSyncTimer = setTimeout(() => {
    fetch("/api/workflow/greeting-selection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ greetingJobIds: ids }),
    }).catch(() => {});
  }, 100);
}

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, null, loadState);
  useEffect(() => { persist(state); }, [state]);

  // 启动时从后端恢复核心工作流数据，清理浏览器缓存后也不丢。
  useEffect(() => {
    Promise.all([
      fetch("/api/workflow/selection").then(r => r.json()).catch(() => ({})),
      fetch("/api/workflow/greeting-selection").then(r => r.json()).catch(() => ({})),
      fetch("/api/resumes/active").then(r => r.json()).catch(() => ({})),
      fetch("/api/resumes/files").then(r => r.json()).catch(() => ({})),
      fetch("/api/jobs/pool?include_hidden=true").then(r => r.json()).catch(() => ({})),
      fetch("/api/diligence/reports").then(r => r.json()).catch(() => ({})),
      fetch("/api/scoring/rankings").then(r => r.json()).catch(() => ({})),
      fetch("/api/greetings/drafts").then(r => r.json()).catch(() => ({})),
      fetch("/api/resumes/optimizations").then(r => r.json()).catch(() => ({})),
      fetch("/api/resumes/chat/load").then(r => r.json()).catch(() => ({})),
    ])
      .then(([selection, greetingSelection, activeResume, files, jobs, diligence, rankings, greetings, optimizations, chats]) => {
        dispatch(actions.hydrateFromBackend({
          selection,
          greetingSelection,
          activeResume,
          files,
          jobs,
          diligence,
          rankings,
          greetings,
          optimizations,
          chats,
        }));
      })
      .catch(() => {})
      .finally(() => { _selectionSyncReady = true; });
  }, []);

  // selectedJobIds 变化时同步到后端
  useEffect(() => {
    syncSelectionToBackend(state.selectedJobIds);
  }, [state.selectedJobIds]);

  // 排序页带入的打招呼目标独立持久化，避免页面切换或本地缓存降级时丢失批次。
  useEffect(() => {
    syncGreetingSelectionToBackend(state.greetingJobIds);
  }, [state.greetingJobIds]);

  return (
    <StateCtx.Provider value={state}>
      <DispatchCtx.Provider value={dispatch}>
        {children}
      </DispatchCtx.Provider>
    </StateCtx.Provider>
  );
}

// ── Hooks ──
export function useWorkflowState() { return useContext(StateCtx); }
export function useWorkflowDispatch() { return useContext(DispatchCtx); }

// ── Convenience action creators ──
export const actions = {
  setResumeProfile: (profile: ResumeProfile | null): Action => ({ type: "SET_RESUME_PROFILE", profile }),
  setUploadedFiles: (files: UploadedFile[]): Action => ({ type: "SET_UPLOADED_FILES", files }),
  toggleJobSelection: (jobId: string): Action => ({ type: "TOGGLE_JOB_SELECTION", jobId }),
  selectAllJobs: (jobIds: string[]): Action => ({ type: "SELECT_ALL_JOBS", jobIds }),
  clearSelection: (): Action => ({ type: "CLEAR_SELECTION" }),
  setSelection: (jobIds: string[]): Action => ({ type: "SET_SELECTION", jobIds }),
  setGreetingSelection: (jobIds: string[]): Action => ({ type: "SET_GREETING_SELECTION", jobIds }),
  setDiligenceReports: (reports: Record<string, DiligenceReport>): Action => ({ type: "SET_DILIGENCE_REPORTS", reports }),
  setRankingResults: (results: RankingResult[]): Action => ({ type: "SET_RANKING_RESULTS", results }),
  setJdAnalyses: (analyses: Record<string, JDAnalysis>): Action => ({ type: "SET_JD_ANALYSES", analyses }),
  setOptimizations: (opts: Record<string, ResumeOptimizationResult>): Action => ({ type: "SET_OPTIMIZATIONS", opts }),
  setGreetingTexts: (texts: Record<string, string>): Action => ({ type: "SET_GREETING_TEXTS", texts }),
  setChatMessages: (msgs: Record<string, Array<{role:string;content:string}>>): Action => ({ type: "SET_CHAT_MESSAGES", msgs }),
  mergeChatMessage: (key: string, messages: Array<{role:string;content:string}> | null): Action => ({ type: "MERGE_CHAT_MESSAGE", key, messages }),
  hydrateFromBackend: (payload: BackendHydrationPayload): Action => ({ type: "HYDRATE_FROM_BACKEND", payload }),
};
