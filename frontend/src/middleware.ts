import { defineMiddleware } from "astro:middleware";

export const onRequest = defineMiddleware(async (_context, next) => {
  const response = await next();

  // Derive the API origin from the public env var so connect-src covers
  // cross-origin API calls in production (frontend on :3000, API on :8000).
  const apiBase = import.meta.env.PUBLIC_API_URL ?? "http://localhost:8000";
  // Only absolute URLs (http/https) produce valid CSP source expressions.
  // Relative paths like "/api" are not valid CSP origins and would be silently
  // ignored by browsers — guard against that misconfiguration.
  let apiOrigin = "";
  try {
    const parsed = new URL(apiBase);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      apiOrigin = parsed.origin;
    }
  } catch {
    // malformed URL — fall back to 'self' only
  }
  const connectSrc = apiOrigin ? `'self' ${apiOrigin}` : "'self'";

  const h = response.headers;
  h.set("X-Frame-Options", "DENY");
  h.set("X-Content-Type-Options", "nosniff");
  h.set("Referrer-Policy", "strict-origin-when-cross-origin");
  h.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  h.set(
    "Content-Security-Policy",
    [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      `connect-src ${connectSrc}`,
      "img-src 'self' data: blob:",
      "worker-src blob:",
      "frame-ancestors 'none'",
    ].join("; "),
  );

  return response;
});
