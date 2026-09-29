# Build from the repository root:
#   docker build -f server/Dockerfile -t neongrid-server .
#   docker run -d --restart unless-stopped -p 47777:47777 neongrid-server
FROM python:3.11-slim
WORKDIR /app
COPY neon_shared ./neon_shared
COPY server/relay_server.py ./relay_server.py
EXPOSE 47777
USER nobody
CMD ["python", "relay_server.py", "--host", "0.0.0.0", "--port", "47777"]
