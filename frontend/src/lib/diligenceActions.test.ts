import { describe, expect, test } from "vitest";
import type { DiligenceReport, JobPosting, JDAnalysis } from "./types";
import { resolveCompanyDiligenceAction, resolveDiligencePrimaryAction, resolveJdAnalysisAction } from "./diligenceActions";

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

  test("first JD analysis only targets selected jobs without an analysis", () => {
    const action = resolveJdAnalysisAction({
      jobs: [job({ id: "job-done" }), job({ id: "job-missing" }), job({ id: "job-unselected" })],
      selectedJobIds: ["job-done", "job-missing"],
      jdAnalyses: { "job-done": analysis() },
    });

    expect(action.label).toBe("一键 JD 分析 (1)");
    expect(action.targetIds).toEqual(["job-missing"]);
  });

  test("first company diligence only targets selected jobs without a report", () => {
    const action = resolveCompanyDiligenceAction({
      jobs: [job({ id: "job-done", company: "已尽调公司" }), job({ id: "job-missing", company: "待尽调公司" })],
      selectedJobIds: ["job-done", "job-missing"],
      diligenceReports: { "已尽调公司": report("已尽调公司") },
    });

    expect(action.label).toBe("一键公司尽调 (1)");
    expect(action.targetIds).toEqual(["job-missing"]);
    expect(action.disabled).toBe(false);
  });

  test("only targets one job when selected jobs belong to the same company", () => {
    const action = resolveCompanyDiligenceAction({
      jobs: [
        job({ id: "job-a", company: "同一公司", company_key: "credit-1" }),
        job({ id: "job-b", company: "同一公司", company_key: "credit-1" }),
      ],
      selectedJobIds: ["job-a", "job-b"],
      diligenceReports: {},
    });

    expect(action.label).toBe("一键公司尽调 (1)");
    expect(action.targetIds).toEqual(["job-a"]);
  });

  test("switches company diligence to rerun for the current selected jobs", () => {
    const action = resolveCompanyDiligenceAction({
      jobs: [job({ id: "job-1", company: "公司一" }), job({ id: "job-2", company: "公司二" }), job({ id: "job-3", company: "未选公司" })],
      selectedJobIds: ["job-1", "job-2"],
      diligenceReports: { "公司一": report("公司一"), "公司二": report("公司二") },
    });

    expect(action.label).toBe("一键重新公司尽调 (2)");
    expect(action.targetIds).toEqual(["job-1", "job-2"]);
  });

  test("only reruns one task for a company with multiple selected jobs", () => {
    const action = resolveCompanyDiligenceAction({
      jobs: [
        job({ id: "job-a", company: "同一公司", company_key: "credit-1" }),
        job({ id: "job-b", company: "同一公司", company_key: "credit-1" }),
      ],
      selectedJobIds: ["job-a", "job-b"],
      diligenceReports: { "credit-1": report("同一公司") },
    });

    expect(action.label).toBe("一键重新公司尽调 (1)");
    expect(action.targetIds).toEqual(["job-a"]);
  });

  test("prioritizes JD analysis when selected jobs have no analysis", () => {
    const action = resolveDiligencePrimaryAction({
      jobs: [job({ id: "job-1" })],
      selectedJobIds: ["job-1"],
      jdAnalyses: {},
      diligenceReports: {},
    });

    expect(action.kind).toBe("analyze_jd");
    expect(action.label).toBe("AI 分析 JD");
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
    expect(action.label).toBe("公司尽调");
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
    expect(action.label).toBe("重新公司尽调");
    expect(action.targetIds).toEqual(["job-1"]);
  });
});
