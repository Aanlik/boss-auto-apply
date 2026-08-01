import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";

describe("Settings panel keyboard regressions", () => {
  test("returns focus to the opening control after the panel closes", () => {
    const panel = readFileSync(resolve(process.cwd(), "src/components/SettingsPanel.tsx"), "utf8");

    expect(panel).toContain("restoreFocusRef");
    expect(panel).toContain("previousActiveElement.focus()");
  });
});
