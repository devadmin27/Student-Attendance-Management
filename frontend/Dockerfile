# ------------------------------------------------------------------
# SAMS — Next.js frontend production image (Coolify deploy)
# Build receives NEXT_PUBLIC_API_BASE_URL as a build ARG (baked into
# the bundle at build time — changing it requires a rebuild).
# Runtime needs no environment variables beyond PORT.
# ------------------------------------------------------------------
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS build
WORKDIR /app
# Next 16 + Tailwind via Turbopack; `base JSX loader` not needed — deps image already has node_modules with dev deps.
ARG NEXT_PUBLIC_API_BASE_URL=https://sams-scphtrang.example/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY . .
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
# Standalone output: server.js + traced runtime files; static assets are copied manually (docs 01-app/03-api-reference/05-config/output.md)
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["sh", "-c", "HOSTNAME=0.0.0.0 PORT=${PORT:-3000} node server.js"]
