# syntax=docker/dockerfile:1.7
#
# Astro standalone Node server. Multi-stage: builder produces the bundle,
# runtime is a small node image with only production deps + the dist/ tree.
# HOST=0.0.0.0 because @astrojs/node defaults to 127.0.0.1 inside the
# container, which would prevent the nginx reverse proxy from reaching it.
#
# We use the Debian-bookworm-slim node image (not -alpine) because the apk
# repos require pre-existing TLS trust, which breaks behind TLS-inspecting
# corporate proxies. Debian's apt is GPG-signed over HTTP and survives
# either way. ~150 MB image vs ~50 MB alpine — acceptable trade.

FROM node:22.22.3-bookworm-slim AS builder

ENV PNPM_HOME="/pnpm" \
    PATH="$PNPM_HOME:$PATH" \
    CI=true \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Optional: trust additional CAs (corporate TLS-inspecting proxies, etc).
# Empty docker/extra-cas/ is a no-op; see docker/extra-cas/README.md.
COPY docker/extra-cas/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates

RUN npm install -g corepack@latest \
    && corepack enable \
    && corepack prepare pnpm@10.33.0 --activate

WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build


FROM node:22.22.3-bookworm-slim AS runtime

ENV HOST=0.0.0.0 \
    PORT=4321 \
    NODE_ENV=production \
    PNPM_HOME="/pnpm" \
    PATH="$PNPM_HOME:$PATH" \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app app

COPY docker/extra-cas/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates

RUN npm install -g corepack@latest \
    && corepack enable \
    && corepack prepare pnpm@10.33.0 --activate

WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --prod --frozen-lockfile

COPY --from=builder /app/dist ./dist

RUN chown -R app:app /app
USER app

EXPOSE 4321

CMD ["node", "./dist/server/entry.mjs"]
