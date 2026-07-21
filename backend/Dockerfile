FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN find /etc/apt/ -name "*.list" -o -name "*.sources" | xargs sed -i 's/deb.debian.org/mirrors.tencent.com/g' && \
    find /etc/apt/ -name "*.list" -o -name "*.sources" | xargs sed -i 's/security.debian.org/mirrors.tencent.com/g'

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip -i https://mirrors.tencent.com/pypi/simple && pip install -r requirements.txt -i https://mirrors.tencent.com/pypi/simple

COPY backend/ ./
COPY config/ /app/config/
RUN mkdir -p /app/data/models /app/data/uploads /app/data/exports
COPY data/models/yolov8n-pose.pt /app/data/models/yolov8n-pose.pt
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
