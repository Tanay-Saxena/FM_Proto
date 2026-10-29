FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Rewrites to the API are fixed at build time, so the backend URL is a build argument.
ARG BACKEND_URL
ENV BACKEND_URL=$BACKEND_URL
RUN npm run build
CMD ["sh", "-c", "npm start -- -p ${PORT:-3000}"]
