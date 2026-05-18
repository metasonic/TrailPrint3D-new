import { defineMiddleware } from "astro:middleware";

export const onRequest = defineMiddleware(async (_context, next) => {
  const response = await next();

  const h = response.headers;
  h.set("X-Frame-Options", "DENY");
  h.set("X-Content-Type-Options", "nosniff");
  h.set("Referrer-Policy", "strict-origin-when-cross-origin");
  h.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  h.set(
    "Content-Security-Policy",
    [
      "default-src 'self'",
      // Astro + React need inline scripts during hydration
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      // API calls go to same origin (proxied) or configured API URL
      "connect-src 'self'",
      // GLB blobs and data URIs for Three.js textures
      "img-src 'self' data: blob:",
      "worker-src blob:",
      "frame-ancestors 'none'",
    ].join("; "),
  );

  return response;
});
