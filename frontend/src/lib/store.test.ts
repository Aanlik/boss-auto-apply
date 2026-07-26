import { describe, expect, test, beforeEach } from "vitest";
import { clearLocalWorkflowStorage } from "./store";

describe("clearLocalWorkflowStorage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  test("removes workflow, active page, hidden tags, and legacy chats", () => {
    window.localStorage.setItem("boss-workbench-state-v4", "{}");
    window.localStorage.setItem("boss-workbench-active-page", "jobs");
    window.localStorage.setItem("boss-workbench-hidden-common-tags", "[]");
    window.localStorage.setItem("chat-demo", "[]");
    window.localStorage.setItem("other-key", "keep");

    clearLocalWorkflowStorage();

    expect(window.localStorage.getItem("boss-workbench-state-v4")).toBeNull();
    expect(window.localStorage.getItem("boss-workbench-active-page")).toBeNull();
    expect(window.localStorage.getItem("boss-workbench-hidden-common-tags")).toBeNull();
    expect(window.localStorage.getItem("chat-demo")).toBeNull();
    expect(window.localStorage.getItem("other-key")).toBe("keep");
  });
});
