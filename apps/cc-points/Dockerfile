# Pointly (cc_points_dashboard) — Next.js 15 + Prisma/SQLite.
# Built natively on pi-node1 (linux/arm64). Build context: ~/apps/cc-points on the Pi —
# source synced from the owner's Mac by scripts/sync-apps.sh, which then copies this
# Dockerfile + the next.config.mjs overlay (adds output:"standalone") on top.
# The SQLite DB lives OUTSIDE the image on a bind mount (/data), see docker-compose.yml.

FROM node:22-bookworm-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# prisma/ must be present before npm ci: the postinstall hook runs `prisma generate`.
COPY package.json package-lock.json ./
COPY prisma ./prisma
# --legacy-peer-deps: next@15.0.3 peer-pins react@19.0.0-rc while the app uses react 19.2.x;
# the owner's own start.sh installs the same way.
RUN npm ci --legacy-peer-deps --no-audit --no-fund
COPY . .
# All pages are force-dynamic, so the build never queries the DB — the URL just has to parse.
ENV DATABASE_URL="file:/data/dev.db"
RUN npm run build

FROM node:22-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    DATABASE_URL="file:/data/dev.db" \
    NEXT_TELEMETRY_DISABLED=1
# openssl: Prisma engine runtime dep. curl: container healthchecks.
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssl curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
# The Prisma query engine is not always traced into the standalone output — copy explicitly.
COPY --from=build /app/node_modules/.prisma ./node_modules/.prisma
# uid 1000 == pi on the host, so the /data bind mount stays writable.
USER node
EXPOSE 3000
CMD ["node", "server.js"]
