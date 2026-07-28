import { expect, test } from "@playwright/test";

test("核心工作台入口可打开并显示流程状态", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("boss 直聘求职端自动化")).toBeVisible();
  await expect(page.getByText("全流程状态")).toBeVisible();
  await page.getByRole("button", { name: "仪表盘" }).click();
  await expect(page.getByText("求职流程仪表盘")).toBeVisible();
});

test("设置面板可以打开维护入口", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /设置/ }).click();
  await expect(page.getByText("完整数据维护")).toBeVisible();
  await expect(page.getByRole("strong").filter({ hasText: "错误诊断中心" })).toBeVisible();
  await expect(page.getByRole("strong").filter({ hasText: "数据清理预演" })).toBeVisible();
  await expect(page.getByRole("link", { name: "下载 CSV 模板" })).toBeVisible();
  await expect(page.getByRole("button", { name: "导出完整数据" })).toBeVisible();
});

test("帮助中心可以打开并展示模块修复动作", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "帮助" }).click();
  await expect(page.getByText("遇到问题，先看这里")).toBeVisible();
  await page.locator(".help-tabs").getByRole("button", { name: "打招呼" }).click();
  await expect(page.getByText("推荐步骤")).toBeVisible();
  await expect(page.getByText("完成信号")).toBeVisible();
  await expect(page.getByText("发送前预检")).toBeVisible();
  await expect(page.getByText("查看失败恢复台")).toBeVisible();
  await expect(page.getByText("灰度模式")).toBeVisible();
});

test("岗位、尽调和排序模块可以依次访问", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "岗位", exact: true }).click();
  await expect(page.getByText("BOSS 直聘岗位抓取与筛选")).toBeVisible();
  await page.getByRole("button", { name: "尽调", exact: true }).click();
  await expect(page.getByText("公司尽调 & JD 分析")).toBeVisible();
  await page.getByRole("button", { name: "排序", exact: true }).click();
  await expect(page.getByRole("heading", { name: "综合排序" })).toBeVisible();
});

test("浏览器上下文可获取内联 PDF 预览", async ({ page }) => {
  const response = await page.request.post("/api/resumes/preview-pdf", {
    data: {
      profile: { name: "张三", title: "产品经理", summary: "负责产品规划与用户增长", skills: [], work_experience: [], education: [], projects: [] },
      optimization: {},
      company: "示例科技",
      job_title: "产品经理",
      template: "modern",
    },
  });

  expect(response.ok()).toBeTruthy();
  expect(response.headers()["content-type"]).toContain("application/pdf");
  expect((await response.body()).subarray(0, 4).toString()).toBe("%PDF");
});

test("浏览器上下文可下载 AI 深度报告 PDF", async ({ page }) => {
  const externalRequests: string[] = [];
  page.on("request", request => {
    if (/api\.deepseek\.com|api\.openai\.com|qianfan\.baidubce\.com|cloudmarket-apigw\.com/.test(request.url())) {
      externalRequests.push(request.url());
    }
  });
  const generated = await page.request.post("/api/assistant/deep-report", {
    data: {
      job: { id: "playwright-report", title: "产品经理", company: "示例科技", jd_text: "负责产品规划" },
      resume: { skills: ["产品规划"] },
      diligence: { companyName: "示例科技", companyScore: 85, riskLevel: "low" },
      ranking: { matchScore: 88, compositeScore: 86 },
    },
  });
  expect(generated.ok()).toBeTruthy();

  const response = await page.request.get("/api/assistant/deep-report/export?job_id=playwright-report&format=pdf");
  expect(response.ok()).toBeTruthy();
  expect(response.headers()["content-type"]).toContain("application/pdf");
  expect((await response.body()).subarray(0, 4).toString()).toBe("%PDF");
  expect(externalRequests).toEqual([]);
});
