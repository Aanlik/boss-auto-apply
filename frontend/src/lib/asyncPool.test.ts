import { describe, expect, test } from "vitest";
import { runWithConcurrency } from "./asyncPool";

describe("runWithConcurrency", () => {
  test("never runs more workers than the configured limit", async () => {
    let active = 0;
    let peak = 0;

    await runWithConcurrency([1, 2, 3, 4, 5], 2, async () => {
      active += 1;
      peak = Math.max(peak, active);
      await new Promise(resolve => setTimeout(resolve, 5));
      active -= 1;
    });

    expect(peak).toBe(2);
  });
});
