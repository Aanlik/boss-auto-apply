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
const STORAGE_KEY = "boss-workbench-state-v4";
const SCHEMA_VERSION = 4;

// ── 空状态 ──
function createEmptyState(): WorkflowState {
  return {
    selectedJobIds: [],
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

// ── Actions ──
type Action =
  | { type: "SET_RESUME_PROFILE"; profile: ResumeProfile | null }
  | { type: "SET_UPLOADED_FILES"; files: UploadedFile[] }
  | { type: "TOGGLE_JOB_SELECTION"; jobId: string }
  | { type: "SELECT_ALL_JOBS"; jobIds: string[] }
  | { type: "CLEAR_SELECTION" }
  | { type: "SET_SELECTION"; jobIds: string[] }
  | { type: "SET_DILIGENCE_REPORTS"; reports: Record<string, DiligenceReport> }
  | { type: "SET_RANKING_RESULTS"; results: RankingResult[] }
  | { type: "SET_JD_ANALYSES"; analyses: Record<string, JDAnalysis> }
  | { type: "SET_OPTIMIZATIONS"; opts: Record<string, ResumeOptimizationResult> }
  | { type: "SET_GREETING_TEXTS"; texts: Record<string, string> }
  | { type: "SET_CHAT_MESSAGES"; msgs: Record<string, Array<{role:string;content:string}>> }
  | { type: "MERGE_CHAT_MESSAGE"; key: string; messages: Array<{role:string;content:string}> | null };

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
    default:
      return state;
  }
}

// ── Context ──
const StateCtx = createContext<WorkflowState>(createEmptyState());
const DispatchCtx = createContext<Dispatch<Action>>(() => {});

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, null, loadState);
  useEffect(() => { persist(state); }, [state]);
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
  setDiligenceReports: (reports: Record<string, DiligenceReport>): Action => ({ type: "SET_DILIGENCE_REPORTS", reports }),
  setRankingResults: (results: RankingResult[]): Action => ({ type: "SET_RANKING_RESULTS", results }),
  setJdAnalyses: (analyses: Record<string, JDAnalysis>): Action => ({ type: "SET_JD_ANALYSES", analyses }),
  setOptimizations: (opts: Record<string, ResumeOptimizationResult>): Action => ({ type: "SET_OPTIMIZATIONS", opts }),
  setGreetingTexts: (texts: Record<string, string>): Action => ({ type: "SET_GREETING_TEXTS", texts }),
  setChatMessages: (msgs: Record<string, Array<{role:string;content:string}>>): Action => ({ type: "SET_CHAT_MESSAGES", msgs }),
  mergeChatMessage: (key: string, messages: Array<{role:string;content:string}> | null): Action => ({ type: "MERGE_CHAT_MESSAGE", key, messages }),
};
