FROM node:20-alpine AS build
WORKDIR /app
RUN corepack enable
COPY apps/web/package.json ./
RUN pnpm install
COPY apps/web ./
RUN pnpm build
EXPOSE 3000
CMD ["pnpm","start"]
