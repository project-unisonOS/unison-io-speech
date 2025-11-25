FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir \
        opentelemetry-api==1.21.0 \
        opentelemetry-sdk==1.21.0 \
        opentelemetry-proto==1.21.0 \
        opentelemetry-exporter-jaeger==1.21.0 \
        opentelemetry-exporter-jaeger-proto-grpc==1.21.0 \
        opentelemetry-exporter-jaeger-thrift==1.21.0 \
        opentelemetry-exporter-otlp==1.21.0 \
        opentelemetry-exporter-otlp-proto-grpc==1.21.0 \
        opentelemetry-exporter-otlp-proto-http==1.21.0 \
        opentelemetry-exporter-otlp-proto-common==1.21.0 \
        opentelemetry-propagator-b3==1.21.0 \
        opentelemetry-propagator-jaeger==1.21.0 \
        opentelemetry-instrumentation-fastapi==0.42b0 \
        opentelemetry-instrumentation-httpx==0.42b0 \
        opentelemetry-instrumentation-asgi==0.42b0 \
        opentelemetry-instrumentation==0.42b0 \
        opentelemetry-semantic-conventions==0.42b0 \
        opentelemetry-util-http==0.42b0 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pytest
COPY src/ ./src/
COPY tests/ ./tests/
EXPOSE 8084
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8084"]
