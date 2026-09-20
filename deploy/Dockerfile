# InsiderTrack MCP server — one small image, no database access, no volumes.
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml VERSION README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && pip install --no-cache-dir uvicorn==0.34.0
RUN useradd --system --no-create-home mcp
USER mcp
EXPOSE 8100
ENV MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8100/health', timeout=3).status == 200 else 1)"
CMD ["insidertrack-mcp"]
