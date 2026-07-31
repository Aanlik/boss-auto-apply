import { describe, expect, test } from "vitest";
import type { DiligenceReport, JobPosting, JDAnalysis } from "./types";
import { resolveDiligencePrimaryAction, resolveJdAnalysisAction } from "./diligenceActions";

function job(overrides: Partial<JobPosting>): JobPosting {
  return {
    id: "job-1",
    title: "产品经理",
    company: "示例科技",
    city: "深圳",
    salary: "",
    salary_min: 0,
    salary_max: 0,
    jd_text: "负责产品规划",
    keywords: [],
    structured_summary: "",
    source: "boss_api",
    source_url: "",
    fetched_at: "",
    dedupe_key: "",
    ...overrides,
  };
}

function analysis(): JDAnalysis {
  return {
    must_have_skills: ["产品规划"],
    nice_to_have_skills: [],
    experience_requirements: [],
    soft_skills: [],
    domain_knowledge: [],
    education_requirements: "",
    summary_text: "负责产品规划",
  };
}

function report(companyName: string): DiligenceReport {
  return {
    companyName,
    companyScore: 80,
    riskLevel: "low",
    basicInfo: { scale: "", funding: "", founded: "", business: "" },
    sentiment: { positive: [], negative: [], evidenceLinks: [] },
    recruitment: { activePositions: 0, salaryCompetitiveness: "", jdQuality: "" },
    industryOutlook: { trend: "", policy: "", marketSpace: "", risks: [] },
    oneLiner: "",
    userNotes: "",
    completedAt: "",
  };
}

describe("resolveDiligencePrimaryAction", () => {
  test("shows one-click JD analysis before selected jobs are analyzed", () => {
    const action = resolveJdAnalysisAction({
      jobs: [job({ id: "job-1" })],
      selectedJobIds: ["job-1"],
      jdAnalyses: {},
    });

    expect(action.label).toBe("一键 JD 分析 (1)");
    expect(action.targetIds).toEqual(["job-1"]);
    expect(action.disabled).toBe(false);
  });

  test("switches to one-click JD reanalysis after selected jobs are analyzed", () => {
    const action = resolveJdAnalysisAction({
      jobs: [job({ id: "job-1" })],
      selectedJobIds: ["job-1"],
      jdAnalyses: { "job-1": analysis() },
    });

    expect(action.label).toBe("一键重新分析 JD (1)");
    expect(action.targetIds).toEqual(["job-1"]);
  });

  test("prioritizes JD analysis when selected jobs have no analysis", () => {
    const action = resolveDiligencePrimaryAction({
      jobs: [job({ id: "job-1" })],
      selectedJobIds: ["job-1"],
      jdAnalyses: {},
      diligenceReports: {},
    });

    expect(action.kind).toBe("analyze_jd");
    expect(action.label).toBe("一键 JD 分析 (1)");
    expect(action.targetIds).toEqual(["job-1"]);
  });

  test("runs diligence after all selected jobs have JD analysis", () => {
    const action = resolveDiligencePrimaryAction({
      jobs: [job({ id: "job-1", company: "示例科技" })],
      selectedJobIds: ["job-1"],
      jdAnalyses: { "job-1": analysis() },
      diligenceReports: {},
    });

    expect(action.kind).toBe("diligence");
    expect(action.label).toBe("一键尽调 (1)");
    expect(action.targetIds).toEqual(["job-1"]);
  });

  test("offers diligence rerun when analysis and diligence are already complete", () => {
    const action = resolveDiligencePrimaryAction({
      jobs: [job({ id: "job-1", company: "示例科技" })],
      selectedJobIds: ["job-1"],
      jdAnalyses: { "job-1": analysis() },
      diligenceReports: { "示例科技": report("示例科技") },
    });

    expect(action.kind).toBe("rediligence");
    expect(action.label).toBe("一键重新公司尽调 (1)");
    expect(action.targetIds).toEqual(["job-1"]);
  });
});
