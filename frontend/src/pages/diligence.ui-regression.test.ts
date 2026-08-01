import { describe, expect, test } from "vitest";
import fs from "node:fs";
import path from "node:path";

const source = fs.readFileSync(path.join(process.cwd(), "src/pages/diligence.tsx"), "utf8");

describe("diligence action layout", () => {
  test("keeps JD analysis and company diligence as separate card actions", () => {
    expect(source).toContain('"AI 分析 JD"');
    expect(source).toContain('"公司尽调"');
    expect(source).not.toContain("runPrimaryActionForJob");
  });

  test("keeps one-click JD and company diligence busy states independent", () => {
    expect(source).toContain("const [jdBatchProgress, setJdBatchProgress]");
    expect(source).toContain("const [companyBatchProgress, setCompanyBatchProgress]");
    expect(source).toContain("const jdActionBusy = jdBatchProgress !== null");
    expect(source).toContain("const companyActionBusy = companyBatchProgress !== null");
  });
});
