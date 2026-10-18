FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src/ ./src/
RUN python -m pip install --no-cache-dir --no-compile -r requirements.lock \
    && python -m pip install --no-cache-dir --no-compile --no-deps .

CMD ["python", "-m", "telegram_bot"]
