# --- 前端 ---
FROM oven/bun:1 AS web
WORKDIR /web
COPY web/package.json ./
RUN bun install
COPY web/ ./
RUN bun run build

# --- 後端 ---
FROM python:3.12-slim
WORKDIR /app
COPY server/pyproject.toml ./
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9" "websockets>=13"
COPY server/banana ./banana
COPY --from=web /web/dist ./web-dist
ENV BANANA_WEB_DIST=/app/web-dist PORT=8000
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "banana.app:app", "--host", "0.0.0.0", "--port", "8000"]
