import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Stitch, StitchToolClient } from "@google/stitch-sdk";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

function loadApiKey() {
  const fromEnv = process.env.STITCH_API_KEY?.trim();
  if (fromEnv) return fromEnv;
  const mcpPath = join(root, ".cursor", "mcp.json");
  const raw = readFileSync(mcpPath, "utf8");
  const cfg = JSON.parse(raw);
  const key = cfg?.mcpServers?.stitch?.headers?.["X-Goog-Api-Key"];
  if (!key) throw new Error("Missing STITCH_API_KEY or .cursor/mcp.json stitch key");
  return String(key).trim();
}

const PROJECT_ID = process.argv[3] || "4977104008355574172";
const SCREEN_ID =
  process.argv[2] || "92b16d38a2564c4faea32f15e9cdc519";

const client = new StitchToolClient({
  apiKey: loadApiKey(),
  baseUrl: "https://stitch.googleapis.com/mcp",
});
const stitch = new Stitch(client);

try {
  const project = stitch.project(PROJECT_ID);
  const screen = await project.getScreen(SCREEN_ID);
  const htmlUrl = await screen.getHtml();
  const imageUrl = await screen.getImage();
  const out = { projectId: PROJECT_ID, screenId: SCREEN_ID, htmlUrl, imageUrl };
  console.log(JSON.stringify(out, null, 2));
} finally {
  await client.close();
}
