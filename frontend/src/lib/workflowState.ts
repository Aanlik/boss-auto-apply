import type {
  DiligenceSnapshot,
  JobPosting,
  MessageDraftSnapshot,
  ResumeSnapshot,
  WorkflowState,
} from "./types";

const STORAGE_KEY = "boss-workbench-state";

function createEmptyWorkflowState(): WorkflowState {
  return {
    selectedJob: null,
    resumeSnapshot: null,
    diligenceSnapshot: null,
    messageDraftSnapshot: null,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isJobPosting(value: unknown): value is JobPosting {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    typeof value.company === "string" &&
    typeof value.city === "string" &&
    typeof value.salary === "string" &&
    typeof value.jd_text === "string"
  );
}

function isResumeSnapshot(value: unknown): value is ResumeSnapshot {
  return isRecord(value) && typeof value.fileName === "string" && typeof value.title === "string" && typeof value.summary === "string";
}

function isDiligenceSnapshot(value: unknown): value is DiligenceSnapshot {
  return isRecord(value) && typeof value.companyName === "string" && typeof value.summary === "string";
}

function isMessageDraftSnapshot(value: unknown): value is MessageDraftSnapshot {
  return isRecord(value) && typeof value.jobId === "string" && typeof value.draftText === "string";
}

export function loadWorkflowState(): WorkflowState {
  if (typeof window === "undefined") {
    return createEmptyWorkflowState();
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return createEmptyWorkflowState();
    }

    const parsed = JSON.parse(raw) as Partial<WorkflowState>;
    return {
      selectedJob: isJobPosting(parsed.selectedJob) ? parsed.selectedJob : null,
      resumeSnapshot: isResumeSnapshot(parsed.resumeSnapshot) ? parsed.resumeSnapshot : null,
      diligenceSnapshot: isDiligenceSnapshot(parsed.diligenceSnapshot) ? parsed.diligenceSnapshot : null,
      messageDraftSnapshot: isMessageDraftSnapshot(parsed.messageDraftSnapshot) ? parsed.messageDraftSnapshot : null,
    };
  } catch {
    return createEmptyWorkflowState();
  }
}

export function saveWorkflowState(state: WorkflowState) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore storage failures in constrained browsers.
  }
}

export function createWorkflowStatePatch(
  state: WorkflowState,
  patch: Partial<WorkflowState>,
): WorkflowState {
  return {
    ...state,
    ...patch,
  };
}
