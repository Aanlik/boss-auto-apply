import { describe, expect, test } from "vitest";
import { ensureDashboardPanelVisible } from "./dashboardPanels";

describe("ensureDashboardPanelVisible", () => {
  test("removes the target panel from hidden panels", () => {
    const config = ensureDashboardPanelVisible({
      order: ["metrics", "review"],
      hidden: ["review"],
    }, "review");

    expect(config).toEqual({
      order: ["metrics", "review"],
      hidden: [],
    });
  });

  test("keeps missing target panels addressable", () => {
    const config = ensureDashboardPanelVisible({
      order: ["metrics"],
      hidden: [],
    }, "review");

    expect(config.order).toEqual(["metrics", "review"]);
  });
});
