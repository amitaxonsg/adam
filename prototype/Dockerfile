FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt
COPY api.py ./
COPY static ./static
RUN useradd -r -u 10001 adam && mkdir -p /data && chown adam:adam /data
USER adam
ENV ADAM_DATA=/data ADAM_MODE=fal
EXPOSE 8000
CMD ["uvicorn","api:app","--host","0.0.0.0","--port","8000","--workers","1"]
