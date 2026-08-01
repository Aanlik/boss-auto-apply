import { describe, expect, test } from "vitest";
import type { DiligenceReport, JobPosting, RankingResult } from "./types";
import { buildDiligenceEvidence, buildRecoveryTasks, buildWorkflowTasks, buildWorkflowTodos, formatApiError } from "./workflowInsights";

function job(overrides: Partial<JobPosting>): JobPosting {
  return {
    id: "job-1",
    title: "产品经理",
    company: "示例科技",
    city: "深圳",
    salary: "20-30K",
    salary_min: 20,
    salary_max: 30,
    jd_text: "",
    keywords: [],
    structured_summary: "",
    source: "boss_api",
    source_url: "",
    fetched_at: "",
    dedupe_key: "",
    ...overrides,
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

function ranking(jobId: string): RankingResult {
  return {
    jobId,
    jobTitle: "产品经理",
    company: "示例科技",
    salary: "20-30K",
    companyScore: 80,
    matchScore: 80,
    compositeScore: 80,
    recommendation: "recommend",
    reason: "",
    matchHighlights: [],
    matchGaps: [],
  };
}

describe("buildWorkflowTasks", () => {
  test("summarizes workflow progress from the user's selected jobs", () => {
    const tasks = buildWorkflowTasks({
      jobs: [
        job({ id: "job-1", company: "A", jd_text: "JD", jd_detail_fetched_at: "2026-08-01T00:00:00Z" }),
        job({ id: "job-2", company: "B" }),
      ],
      selectedJobIds: ["job-1"],
      greetingJobIds: ["job-1"],
      diligenceReports: { A: report("A") },
      rankingResults: [ranking("job-1")],
    });

    expect(tasks.map(t => [t.key, t.status, t.done, t.total])).toEqual([
      ["jobs", "done", 2, 2],
      ["jd", "done", 1, 1],
      ["diligence", "done", 1, 1],
      ["ranking", "done", 1, 1],
      ["greeting", "idle", 0, 1],
    ]);
    expect(tasks[0]).toMatchObject({ label: "全库" });
  });

  test("does not mark selected jobs as JD-complete from another job's detail", () => {
    const jd = buildWorkflowTasks({
      jobs: [
        job({ id: "selected", company: "A" }),
        job({ id: "not-selected", company: "B", jd_text: "完整 JD" }),
      ],
      selectedJobIds: ["selected"],
      greetingJobIds: [],
      diligenceReports: {},
      rankingResults: [],
    }).find(task => task.key === "jd");

    expect(jd).toMatchObject({ done: 0, total: 1, status: "idle" });
  });

  test("requires a fetched JD detail rather than an AI analysis cache", () => {
    const jd = buildWorkflowTasks({
      jobs: [job({ id: "selected", company: "A", jd_text: "只有分析缓存，没有详情抓取时间" })],
      selectedJobIds: ["selected"],
      greetingJobIds: [],
      diligenceReports: {},
      rankingResults: [],
    }).find(task => task.key === "jd");

    expect(jd).toMatchObject({ done: 0, total: 1, status: "idle" });
  });

  test("counts greeting progress against jobs selected on the ranking page", () => {
    const input = {
      jobs: [job({ id: "job-1" }), job({ id: "job-2" })],
      selectedJobIds: ["job-1", "job-2"],
      greetingJobIds: ["job-2"],
      diligenceReports: {},
      rankingResults: [ranking("job-1"), ranking("job-2")],
      greetingTexts: { "job-2": "您好，我对贵司岗位很感兴趣，期待进一步沟通。" },
    };

    const greeting = buildWorkflowTasks(input).find(task => task.key === "greeting");

    expect(greeting).toMatchObject({ done: 1, total: 1, status: "done" });
  });
});

describe("buildWorkflowTodos", () => {
  test("suggests the next useful action from selected jobs", () => {
    const todos = buildWorkflowTodos({
      jobs: [
        job({ id: "job-1", company: "A", jd_text: "" }),
        job({ id: "job-2", company: "B", jd_text: "完整 JD" }),
      ],
      selectedJobIds: ["job-1", "job-2"],
      greetingJobIds: ["job-1", "job-2"],
      diligenceReports: { B: report("B") },
      rankingResults: [],
      greetingTexts: {},
    });

    expect(todos.map(todo => [todo.key, todo.page, todo.count])).toEqual([
      ["missing_jd", "jobs", 1],
      ["missing_diligence", "diligence", 1],
      ["missing_ranking", "ranking", 2],
      ["missing_greeting", "greeting", 2],
    ]);
  });
});

describe("formatApiError", () => {
  test("uses structured API error message and action when present", () => {
    const message = formatApiError({
      detail: { code: "BOSS_NOT_LOGIN", message: "需要先登录 BOSS", action: "打开登录" },
    });

    expect(message).toBe("需要先登录 BOSS · 建议: 打开登录");
  });
});

describe("buildDiligenceEvidence", () => {
  test("collects business api fields, search links and ai signals", () => {
    const evidence = buildDiligenceEvidence({
      ...report("示例科技有限公司"),
      businessInfo: {
        companyName: "示例科技有限公司",
        legalRepresentative: "张三",
        registrationCapital: "1000万人民币",
        paidInCapital: "",
        establishedDate: "2018-01-01",
        businessStatus: "存续",
        unifiedCreditCode: "91410100TEST",
        registrationNumber: "",
        taxpayerId: "",
        businessScope: "电子商务",
        industry: "批发和零售业",
        address: "",
        shareholders: [],
        executives: [],
        branchCount: 0,
        abnormalInfo: ["列入经营异常"],
        penalties: [],
        annualReport: "",
      },
      sentiment: {
        positive: ["口碑稳定"],
        negative: ["投诉较多"],
        evidenceLinks: ["https://example.com/news"],
      },
    });

    expect(evidence.business).toContain("工商名称: 示例科技有限公司");
    expect(evidence.business).toContain("统一信用代码: 91410100TEST");
    expect(evidence.risk).toContain("列入经营异常");
    expect(evidence.searchLinks).toEqual(["https://example.com/news"]);
    expect(evidence.aiSignals).toEqual(["正面: 口碑稳定", "负面: 投诉较多"]);
    expect(evidence.sourceTrust).toEqual([
      { label: "工商 API", level: "high", description: "工商登记、司法风险和经营异常来自结构化接口，适合作为事实依据。" },
      { label: "搜索证据", level: "medium", description: "搜索链接用于交叉验证舆情，需要人工打开复核发布时间和来源。" },
      { label: "AI 归纳", level: "assistive", description: "AI 只负责压缩和解释信号，不能替代原始证据。" },
    ]);
  });
});

describe("buildRecoveryTasks", () => {
  test("keeps failed and partial failed workflow tasks with recovery actions", () => {
    const recovery = buildRecoveryTasks([
      {
        id: "task-1",
        type: "jd_enrich",
        title: "获取 JD 详情",
        status: "failed",
        done: 0,
        total: 3,
        message: "BOSS 登录已失效",
        errorCode: "BOSS_NOT_LOGIN",
        action: "重新登录 BOSS 后重试",
        retryable: true,
        createdAt: "",
        updatedAt: "2026-07-27T10:00:00Z",
      },
      {
        id: "task-2",
        type: "ranking",
        title: "综合排序",
        status: "completed",
        done: 2,
        total: 2,
        message: "完成",
        errorCode: "",
        action: "",
        retryable: false,
        createdAt: "",
        updatedAt: "2026-07-27T09:00:00Z",
      },
    ]);

    expect(recovery).toEqual([
      {
        id: "task-1",
        title: "获取 JD 详情",
        message: "BOSS 登录已失效",
        action: "重新登录 BOSS 后重试",
        retryable: true,
        status: "failed",
      },
    ]);
  });
});
