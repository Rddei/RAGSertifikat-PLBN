# syntax=docker/dockerfile:1
# Multi-stage build untuk Next.js (mode standalone).

# ---------- 1) Dependencies ----------
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---------- 2) Builder ----------
FROM node:22-alpine AS builder
WORKDIR /app

# PENTING: NEXT_PUBLIC_* dibaca browser & di-"bake" saat build.
# Jadi nilainya harus URL yang bisa diakses DARI BROWSER (bukan nama service docker).
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---------- 3) Runner ----------
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# User non-root
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

# Aset publik + output standalone
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
