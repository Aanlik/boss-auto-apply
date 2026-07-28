import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: {
    command: "cd ../backend && BOSS_WORKBENCH_TEST_MODE=1 python3 -m uvicorn app.main:app --host 127.0.0.1 --port 5174",
    url: "http://127.0.0.1:5174/health",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
