# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv package manager for faster dependency installation
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml ./
COPY LICENSE ./
COPY README.md ./
COPY env.template ./
COPY src/ ./src/

# Install dependencies using uv
RUN uv pip install --system --no-cache -e .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' mcp && \
    chown -R mcp:mcp /app

# Set environment variables (users must provide CANVAS_API_TOKEN and CANVAS_API_URL at runtime)
# Example: docker run -e CANVAS_API_TOKEN=xyz -e CANVAS_API_URL=https://... canvas-mcp
ENV MCP_SERVER_NAME="canvas-mcp" \
    ENABLE_DATA_ANONYMIZATION="false" \
    ANONYMIZATION_DEBUG="false"

# Switch to non-root user
USER mcp

# In stdio mode this is a no-op (no port listening). In http mode (set via
# MCP_TRANSPORT=http at runtime, e.g. via fly.toml [env]) the server binds to
# MCP_BIND_PORT (default 8000) on 0.0.0.0.
EXPOSE 8000

# Health check to verify installation
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import canvas_mcp; print('OK')" || exit 1

# Run the MCP server. Default behavior is stdio (back-compat); set
# MCP_TRANSPORT=http in the runtime env to switch to streamable-HTTP mode.
CMD ["canvas-mcp-server"]
