FROM python:3.12-slim AS core
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/agentcut
COPY AgentCut/ ./
RUN python -m pip install --no-cache-dir .
WORKDIR /work
ENTRYPOINT ["agentcut"]
CMD ["modules"]

FROM core AS render
RUN python -m pip install --no-cache-dir '/opt/agentcut[render]'

FROM render AS api
RUN python -m pip install --no-cache-dir '/opt/agentcut[api]'
# Start explicitly with: serve /work/PROJECT --host 0.0.0.0
