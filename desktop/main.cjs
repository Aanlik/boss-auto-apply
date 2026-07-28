const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");

let backendProcess = null;
let mainWindow = null;

function repoRoot() {
  return path.resolve(__dirname, "..");
}

function backendExecutablePath() {
  const executable = process.platform === "win32" ? "boss-workbench-backend.exe" : "boss-workbench-backend";
  const root = app.isPackaged ? process.resourcesPath : repoRoot();
  const backendRoot = app.isPackaged ? path.join(root, "backend") : path.join(root, "dist-desktop", "backend");
  const candidates = [
    path.join(backendRoot, "boss-workbench-backend", executable),
    path.join(backendRoot, executable),
  ];
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  if (found) return found;
  if (app.isPackaged) {
    return candidates[0];
  }
  return candidates[0];
}

function bundledBrowserExecutablePath() {
  const browserRoot = app.isPackaged
    ? path.join(process.resourcesPath, "browser")
    : path.join(repoRoot(), "dist-desktop", "browser");
  const manifestPath = path.join(browserRoot, "browser-manifest.json");
  if (!fs.existsSync(manifestPath)) return "";
  try {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    const executable = path.join(browserRoot, manifest.executableRelativePath || "");
    return fs.existsSync(executable) ? executable : "";
  } catch {
    return "";
  }
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
  });
}

function waitForHealth(port, timeoutMs = 45000) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get({ host: "127.0.0.1", port, path: "/health", timeout: 1000 }, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          resolve();
        } else if (Date.now() - startedAt > timeoutMs) {
          reject(new Error(`后端启动超时，健康检查状态 ${res.statusCode}`));
        } else {
          setTimeout(tick, 500);
        }
      });
      req.on("error", () => {
        if (Date.now() - startedAt > timeoutMs) {
          reject(new Error("后端启动超时，无法连接本地服务"));
        } else {
          setTimeout(tick, 500);
        }
      });
      req.on("timeout", () => req.destroy());
    };
    tick();
  });
}

async function startBackend() {
  const backendPath = backendExecutablePath();
  if (!fs.existsSync(backendPath)) {
    throw new Error(`未找到内置后端：${backendPath}`);
  }
  const port = await findFreePort();
  const dataDir = path.join(app.getPath("userData"), "data");
  const browserPath = bundledBrowserExecutablePath();
  fs.mkdirSync(dataDir, { recursive: true });
  backendProcess = spawn(backendPath, [], {
    env: {
      ...process.env,
      BOSS_WORKBENCH_PORT: String(port),
      BOSS_WORKBENCH_DATA_DIR: dataDir,
      BOSS_WORKBENCH_DESKTOP: "1",
      ...(browserPath ? { BOSS_WORKBENCH_BROWSER_EXECUTABLE: browserPath } : {}),
    },
    stdio: app.isPackaged ? "ignore" : "inherit",
  });
  backendProcess.on("exit", (code) => {
    if (code !== 0 && mainWindow) {
      mainWindow.webContents.send("backend-exit", code);
    }
  });
  await waitForHealth(port);
  return port;
}

function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 900,
    minWidth: 1080,
    minHeight: 720,
    title: "boss 直聘求职端自动化",
    backgroundColor: "#f7f8fb",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });
  mainWindow.loadURL(`http://127.0.0.1:${port}`);
}

async function boot() {
  try {
    const port = await startBackend();
    createWindow(port);
  } catch (error) {
    dialog.showErrorBox("boss 直聘求职端自动化启动失败", error instanceof Error ? error.message : String(error));
    app.quit();
  }
}

app.whenReady().then(boot);

app.on("window-all-closed", () => {
  app.quit();
});

app.on("before-quit", () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});
