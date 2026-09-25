FROM python:3.11-slim

# 系统 CBC 求解器；PuLP 亦自带 CBC 二进制作为回退。
RUN apt-get update \
    && apt-get install -y --no-install-recommends coinor-cbc \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests
COPY scripts ./scripts

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=5s \
    CMD python -c "import json,urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); sys.exit(0 if json.load(r)['status']=='ok' else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
