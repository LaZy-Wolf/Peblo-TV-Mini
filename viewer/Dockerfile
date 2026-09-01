# Build the static bundle, then serve it with nginx. The API base URL is a
# build argument because Vite inlines it at build time.
FROM node:20-alpine AS build
WORKDIR /app
COPY viewer/package.json viewer/package-lock.json ./
RUN npm ci
COPY viewer ./
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY viewer/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
