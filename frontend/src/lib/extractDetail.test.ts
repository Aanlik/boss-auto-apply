import fs from "node:fs";
import path from "node:path";
import { JSDOM } from "jsdom";
import { describe, expect, test } from "vitest";

const script = fs.readFileSync(
  path.resolve(__dirname, "../../..", "backend/app/services/extract_detail.js"),
  "utf8",
);

function extractFromHtml(html: string) {
  const dom = new JSDOM(html, { runScripts: "outside-only", url: "https://www.zhipin.com/job_detail/demo.html" });
  Object.defineProperty(dom.window.Element.prototype, "innerText", {
    configurable: true,
    get() {
      return this.textContent || "";
    },
  });
  const result = dom.window.eval(script);
  return JSON.parse(String(result));
}

describe("extract_detail.js", () => {
  test("prefers the registered company name from business information", () => {
    const result = extractFromHtml(`
      <main>
        <section class="job-detail-section">
          <h3>职位描述</h3>
          <p>负责产品规划和需求分析。</p>
          <p>工商信息</p>
        </section>
        <section class="company-info">
          <a>奇胜生物</a>
          <div>公司全称 示例生物科技有限公司 法定代表人 张三</div>
        </section>
      </main>
    `);

    expect(result.company_name).toBe("示例生物科技有限公司");
  });

  test("removes benefit and recruiter noise from jd text", () => {
    const result = extractFromHtml(`
      <main>
        <section class="job-detail-section">
          职位描述
          负责产品规划和需求分析。
          职位亮点
          五险一金
          张女士
          今日活跃
          示例科技 · 人事专员
          工作地址
          深圳南山区
        </section>
      </main>
    `);

    expect(result.jd).toContain("负责产品规划和需求分析。");
    expect(result.jd).not.toContain("职位亮点");
    expect(result.jd).not.toContain("五险一金");
    expect(result.jd).not.toContain("张女士");
    expect(result.jd).not.toContain("工作地址");
  });

  test("removes category marketing and online noise before real jd sections", () => {
    const result = extractFromHtml(`
      <main>
        <section class="job-detail-section">
          职位描述
          组织发展
          招聘
          人才发展
          教育
          医疗健康
          电商
          1100人 + 11层楼 + 成立15年 = ？
          答案是：郑州护肤头部，年会发8辆宝马车的我们
          我们能给你什么？
          短期+中期+长期收入，综合回报打败市场90%企业
          和业务平行的权利，给予足够授权，由总经理直管
          个人成长（每2-3个月一次调薪）
          HRBP → HRBP主管 →总助 → 项目负责人 →总经理
          职责
          负责组织发展体系建设，推动人才盘点和干部培养。
          任职要求：
          5年以上组织发展或HRBP经验。
          我们是谁？
          制度完善，福利齐全，晋升公平。
          在线
        </section>
      </main>
    `);

    expect(result.jd).toContain("职责");
    expect(result.jd).toContain("负责组织发展体系建设");
    expect(result.jd).not.toContain("1100人 + 11层楼");
    expect(result.jd).not.toContain("年会发8辆宝马");
    expect(result.jd).not.toContain("我们能给你什么");
    expect(result.jd).not.toContain("我们是谁");
    expect(result.jd).not.toContain("HRBP → HRBP主管");
    expect(result.jd).not.toContain("在线");
  });
});
