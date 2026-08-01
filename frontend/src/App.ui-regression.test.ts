import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";

describe("global workflow status copy", () => {
  test("does not call incomplete business work a normal system state", () => {
    const app = readFileSync(resolve(process.cwd(), "src/App.tsx"), "utf8");

    expect(app).toMatch(/服务正常 · 业务待推进/);
    expect(app).toMatch(/const hasBusinessTodos/);
    expect(app).not.toMatch(/岗位池到打招呼 · 系统\{healthCheck\?\.status === "ok" \? "正常"/);
  });

  test("keeps the full-pool status card aligned with the other compact cards", () => {
    const app = readFileSync(resolve(process.cwd(), "src/lib/workflowInsights.ts"), "utf8");
    const styles = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");

    expect(app).toContain('label: "全库"');
    expect(styles).not.toContain(".workflow-status-card--jobs");
  });
});
