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

  test("lets users clear the displayed greeting skip reasons", () => {
    const greeting = readProjectFile("src/pages/greeting.tsx");

    expect(greeting).toMatch(/清空跳过原因/);
    expect(greeting).toMatch(/setCandidateResult\(previous/);
  });

  test("does not present automatic sending as available before BOSS login passes", () => {
    const greeting = readProjectFile("src/pages/greeting.tsx");

    expect(greeting).toMatch(/isAutoSendReady/);
    expect(greeting).toMatch(/"不可发送"/);
    expect(greeting).toMatch(/BOSS 登录未验证/);
  });

  test("masks sensitive details in a greeting until the user explicitly enters edit mode", () => {
    const greeting = readProjectFile("src/pages/greeting.tsx");

    expect(greeting).toMatch(/maskGreetingSensitiveText/);
    expect(greeting).toMatch(/编辑完整话术/);
    expect(greeting).toMatch(/显示已脱敏内容/);
    expect(greeting).toMatch(/邮箱\\s\*\[:：\]/);
  });

  test("shows the actual automatic-send blocker and exposes preflight beside the disabled action", () => {
    const greeting = readProjectFile("src/pages/greeting.tsx");

    expect(greeting).toMatch(/formatSafetyCheckMessage/);
    expect(greeting).toMatch(/return check\.message/);
    expect(greeting).toMatch(/发送前预检/);
    expect(greeting).not.toMatch(/灰度记录已通过，但当前不可发送/);
  });

  test("shows the saved frequency profile as the selected option", () => {
    const greeting = readProjectFile("src/pages/greeting.tsx");

    expect(greeting).toMatch(/const selectedFrequencyProfile = useMemo/);
    expect(greeting).toMatch(/value=\{selectedFrequencyProfile\}/);
    expect(greeting).not.toMatch(/defaultValue=""/);
  });

  test("uses a unique key when a job has duplicate custom tags", () => {
    const greeting = readProjectFile("src/pages/greeting.tsx");

    expect(greeting).toContain("key={`${job.id}-${tag}-${index}`}");
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
