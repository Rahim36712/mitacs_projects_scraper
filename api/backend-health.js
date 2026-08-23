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
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed. Use GET." });
  }

  const backend = getBackendUrl(req);
  if (!backend) {
    return res.status(500).json({
      status: "error",
      error: "SCRAPER_BACKEND_URL is not configured in Vercel project settings.",
    });
  }

  try {
    const response = await fetch(`${backend}/api/health`);
    const data = await response.json();
    if (!response.ok) {
      return res.status(response.status).json({
        status: "error",
        error: data.error || "Backend health check failed.",
        backend,
      });
    }

    return res.status(200).json({
      status: data.status || "ok",
      backend,
    });
  } catch (error) {
    return res.status(502).json({
      status: "error",
      error: `Cannot reach backend: ${error.message}`,
      backend,
    });
  }
};
