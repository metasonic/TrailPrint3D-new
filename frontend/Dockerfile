FROM node:22-slim AS builder

WORKDIR /app
COPY frontend/package.json ./
RUN npm install --frozen-lockfile

COPY frontend/ ./
ARG PUBLIC_API_URL=http://localhost:8000
ENV PUBLIC_API_URL=${PUBLIC_API_URL}
RUN npm run build

# ── Runtime ──────────────────────────────────────────────────────────────────
FROM node:22-slim

WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

ENV HOST=0.0.0.0
ENV PORT=3000
EXPOSE 3000
CMD ["node", "dist/server/entry.mjs"]
