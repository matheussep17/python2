import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(frontendDirectory, "..");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5180",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: ".\\.venv\\Scripts\\python.exe -m uvicorn saas_server.api:app --host 127.0.0.1 --port 8001",
      cwd: projectRoot,
      url: "http://127.0.0.1:8001/health",
      reuseExistingServer: false,
      env: { IGREJA_SAAS_DB: path.join(projectRoot, "saas_server", "data", "playwright.db"), IGREJA_SAAS_TEST_MODE: "1" },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5180",
      cwd: frontendDirectory,
      url: "http://127.0.0.1:5180",
      reuseExistingServer: false,
      env: { VITE_API_URL: "http://127.0.0.1:8001" },
    },
  ],
});