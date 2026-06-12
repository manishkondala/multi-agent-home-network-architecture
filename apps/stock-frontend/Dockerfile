# stock_analysis frontend — Vite/React build served by nginx, which also proxies /api
# to the stock-backend container over the fleet network (same-origin: no CORS, no
# hardcoded backend URL in the bundle — the app's axios baseURL is the relative "/api").
# Built natively on pi-node1 (linux/arm64). Context: ~/apps/stock-analysis/frontend.

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
