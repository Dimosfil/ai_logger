FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir '.[postgres]'
ENV PYTHONUNBUFFERED=1 AI_LOGGER_SERVER_HOST=0.0.0.0 AI_LOGGER_SERVER_PORT=8765
EXPOSE 8765
CMD ["ai-logger-server"]
