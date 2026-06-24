# syntax=docker/dockerfile:1

# Stage 1: Build the Next.js frontend (when the frontend/ directory exists)
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Copy the entire project so the frontend directory is available if it exists.
COPY . .

# Build the Next.js standalone output only when the frontend has been created.
# The standalone output is copied to /built-frontend so the final stage can
# always consume it, even if the frontend is not present yet.
RUN if [ -f frontend/package.json ]; then \
      cd frontend && \
      npm install && \
      npm run build && \
      mkdir -p /built-frontend && \
      cp -a .next/standalone/. /built-frontend/ && \
      cp -a .next/static /built-frontend/.next/static && \
      if [ -d public ]; then cp -a public/. /built-frontend/public/; fi; \
    else \
      mkdir -p /built-frontend; \
    fi

# Stage 2: Final Python runtime with Node.js for the Next.js standalone server
FROM python:3.11-alpine

LABEL maintainer="netrunner"
LABEL description="NetRunner - SSH orchestration for local IT infrastructure with Next.js frontend"

WORKDIR /app

# Install system tools, SSH client, and Node.js runtime for the Next.js server
RUN apk add --no-cache openssh-client sshpass iputils nodejs npm

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source
COPY . .

# Apply the Docker-specific configuration and create persistent directories
RUN cp config_docker.py config.py && \
    mkdir -p /app/data /app/keys /app/reports /app/modules && \
    chmod +x /app/startup.sh

# Copy the built Next.js frontend (empty when the frontend has not been built yet)
COPY --from=frontend-builder /built-frontend /app/frontend

VOLUME ["/app/data", "/app/keys", "/app/reports", "/app/modules"]

# Only the Next.js frontend port is exposed; the Python backend is reachable internally
EXPOSE 3000

CMD ["/app/startup.sh"]
