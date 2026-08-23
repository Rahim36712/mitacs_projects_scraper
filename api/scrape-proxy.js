const DEFAULT_TIMEOUT_MS = 300000;

function getBackendUrl(req) {
  const override = (req.headers["x-backend-url"] || "").trim();
  if (override) {
    return override.replace(/\/+$/, "");
  }
  const configured = (process.env.SCRAPER_BACKEND_URL || "").trim();
  if (!configured) {
    return "";
  }
  return configured.replace(/\/+$/, "");
}

module.exports = async function handler(req, res) {
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Backend-Url");
    res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
    return res.status(204).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed. Use POST." });
  }

  const backend = getBackendUrl(req);
  if (!backend) {
    return res.status(500).json({
      error: "SCRAPER_BACKEND_URL is not configured in Vercel project settings.",
    });
  }

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
    const response = await fetch(`${backend}/api/scrape`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(req.body || {}),
      signal: controller.signal,
    });
    clearTimeout(timer);

    const contentType = response.headers.get("content-type") || "application/json";
    res.setHeader("Content-Type", contentType);
    res.status(response.status).send(await response.text());
  } catch (error) {
    const message = error && error.name === "AbortError"
      ? "Proxy request timed out while scraping."
      : `Proxy error: ${error.message}`;
    res.status(502).json({ error: message });
  }
};
