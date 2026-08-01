import { describe, expect, test, beforeEach } from "vitest";
import { clearLocalWorkflowStorage, hydrateWorkflowStateFromBackend } from "./store";
import type { DiligenceReport } from "./types";

describe("clearLocalWorkflowStorage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  test("removes workflow, active page, hidden tags, and legacy chats", () => {
    window.localStorage.setItem("boss-workbench-state-v4", "{}");
    window.localStorage.setItem("boss-workbench-active-page", "jobs");
    window.localStorage.setItem("boss-workbench-hidden-common-tags", "[]");
    window.localStorage.setItem("chat-demo", "[]");
    window.localStorage.setItem("other-key", "keep");

    clearLocalWorkflowStorage();

    expect(window.localStorage.getItem("boss-workbench-state-v4")).toBeNull();
    expect(window.localStorage.getItem("boss-workbench-active-page")).toBeNull();
    expect(window.localStorage.getItem("boss-workbench-hidden-common-tags")).toBeNull();
    expect(window.localStorage.getItem("chat-demo")).toBeNull();
    expect(window.localStorage.getItem("other-key")).toBe("keep");
  });
});

describe("hydrateWorkflowStateFromBackend", () => {
  test("restores workflow state from backend-backed resources after cache is cleared", () => {
    const state = {
      selectedJobIds: [],
      greetingJobIds: ["job-2"],
      resumeProfile: null,
      uploadedFiles: [],
      diligenceReports: {},
      rankingResults: [],
      jdAnalyses: {},
      optimizations: {},
      greetingTexts: {},
      chatMessages: {},
    };

    const hydrated = hydrateWorkflowStateFromBackend(state, {
      selection: { selectedJobIds: ["job-1"] },
      greetingSelection: { greetingJobIds: ["job-3", "job-4"] },
      activeResume: { profile: { name: "张三" } },
      files: { files: [{ id: "resume-1", filename: "resume.pdf" }] },
      jobs: { jobs: [{ id: "job-1", jd_analysis: { summary_text: "岗位分析" } }] },
      diligence: { reports: { 示例科技: { companyName: "示例科技", companyScore: 80 } } },
      rankings: { rankings: [{ jobId: "job-1", compositeScore: 88 }] },
      greetings: { greetings: { "job-1": "您好" } },
      optimizations: { optimizations: { "job-1": { tailored_summary: "优化摘要" } } },
      chats: { chats: { "greet-opt-job-1": [{ role: "user", content: "改一下" }] } },
    });

    expect(hydrated.selectedJobIds).toEqual(["job-1"]);
    expect(hydrated.greetingJobIds).toEqual(["job-3", "job-4"]);
    expect(hydrated.resumeProfile?.name).toBe("张三");
    expect(hydrated.uploadedFiles[0].id).toBe("resume-1");
    expect(hydrated.jdAnalyses["job-1"].summary_text).toBe("岗位分析");
    expect(hydrated.diligenceReports["示例科技"].companyScore).toBe(80);
    expect(hydrated.rankingResults[0].compositeScore).toBe(88);
    expect(hydrated.greetingTexts["job-1"]).toBe("您好");
    expect(hydrated.optimizations["job-1"].tailored_summary).toBe("优化摘要");
    expect(hydrated.chatMessages["greet-opt-job-1"][0].content).toBe("改一下");
  });

  test("uses an explicit empty greeting selection from the backend to clear stale local targets", () => {
    const state = {
      selectedJobIds: ["job-1"],
      greetingJobIds: ["job-2", "job-3"],
      resumeProfile: null,
      uploadedFiles: [],
      diligenceReports: {},
      rankingResults: [],
      jdAnalyses: {},
      optimizations: {},
      greetingTexts: {},
      chatMessages: {},
    };

    const hydrated = hydrateWorkflowStateFromBackend(state, {
      greetingSelection: { greetingJobIds: [] },
    });

    expect(hydrated.greetingJobIds).toEqual([]);
  });

  test("replaces stale cached diligence reports and drafts with backend records", () => {
    const state = {
      selectedJobIds: [], greetingJobIds: [], resumeProfile: null, uploadedFiles: [],
      diligenceReports: { 旧公司: { companyName: "旧公司", companyScore: 99 } as DiligenceReport }, rankingResults: [], jdAnalyses: {},
      optimizations: {}, greetingTexts: { "old-job": "旧话术" }, chatMessages: {},
    };

    const hydrated = hydrateWorkflowStateFromBackend(state, {
      diligence: { reports: { 新公司: { companyName: "新公司", companyScore: 80 } as DiligenceReport } },
      greetings: { greetings: { "new-job": "新话术" } },
    });

    expect(hydrated.diligenceReports).toEqual({ 新公司: { companyName: "新公司", companyScore: 80 } });
    expect(hydrated.greetingTexts).toEqual({ "new-job": "新话术" });
  });
});
