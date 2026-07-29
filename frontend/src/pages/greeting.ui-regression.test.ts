import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";

function readProjectFile(path: string) {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

function cssRule(selector: string) {
  const css = readProjectFile("src/styles.css");
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`${escaped}\\s*{(?<body>[^}]*)}`))?.groups?.body || "";
}

describe("Greeting UI regressions", () => {
  test("removes the greeting failure recovery desk from frontend code", () => {
    const greeting = readProjectFile("src/pages/greeting.tsx");
    const api = readProjectFile("src/lib/api.ts");
    const types = readProjectFile("src/lib/types.ts");

    expect(greeting).not.toMatch(/失败恢复台|刷新失败恢复|getGreetingRecoveryPanel|recoveryPanel/);
    expect(api).not.toMatch(/getGreetingRecoveryPanel|\/api\/greetings\/recovery-panel/);
    expect(types).not.toMatch(/GreetingRecoveryPanel/);
  });

  test("keeps the PDF preview close button above the embedded PDF viewer", () => {
    const overlayRule = cssRule(".pdf-preview-overlay");
    const closeRule = cssRule(".pdf-preview-close");
    const dialogRule = cssRule(".pdf-preview-dialog");
    const closeZ = Number(closeRule.match(/z-index\s*:\s*(\d+)/)?.[1] || 0);
    const dialogZ = Number(dialogRule.match(/z-index\s*:\s*(\d+)/)?.[1] || 0);

    expect(overlayRule).toMatch(/position\s*:\s*fixed/);
    expect(closeRule).toMatch(/position\s*:\s*fixed/);
    expect(closeZ).toBeGreaterThan(dialogZ);
  });
});
