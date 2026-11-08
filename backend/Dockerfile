FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY backend/src ./src
COPY backend/tests ./tests
COPY models ./models

EXPOSE 8000

CMD ["uvicorn", "src.main:src", "--host", "0.0.0.0", "--port", "8000"]

