import { describe, expect, it } from "vitest";
import { groupJobsByCompany } from "./jobGrouping";

const job = (id: string, company: string, company_key?: string) => ({
  id,
  title: id,
  company,
  company_key,
});

describe("groupJobsByCompany", () => {
  it("groups jobs by company key while preserving every original job", () => {
    const groups = groupJobsByCompany([
      job("job-1", "示例科技", "credit-1"),
      job("job-2", "示例科技", "credit-1"),
      job("job-3", "另一家公司", "credit-2"),
    ]);

    expect(groups).toHaveLength(2);
    expect(groups[0].company).toBe("示例科技");
    expect(groups[0].jobs.map(item => item.id)).toEqual(["job-1", "job-2"]);
    expect(groups[1].jobs.map(item => item.id)).toEqual(["job-3"]);
  });

  it("falls back to a normalized company name when company key is absent", () => {
    const groups = groupJobsByCompany([
      job("job-1", " 示例科技 "),
      job("job-2", "示例科技"),
      job("job-3", "另一家公司"),
    ]);

    expect(groups).toHaveLength(2);
    expect(groups[0].jobs.map(item => item.id)).toEqual(["job-1", "job-2"]);
  });
});
