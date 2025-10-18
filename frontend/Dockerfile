FROM node:20-slim AS builder

ARG BLANK_API_URL

RUN npm install -g pnpm

WORKDIR /app

# Copy lockfile and package files
COPY frontend/package.json .
COPY frontend/pnpm-lock.yaml .

RUN pnpm install --frozen-lockfile

COPY frontend/ .

ENV VITE_BLANK_API_URL=${BLANK_API_URL}
RUN pnpm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
