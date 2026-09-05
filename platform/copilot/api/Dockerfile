# supplies python version 3.12 and pip package manager
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

#installs FastAPI and Uvicorn
RUN pip install \
    --no-cache-dir \
    --requirement requirements.txt

#adds the application code to the image
COPY app ./app

RUN useradd --create-home --uid 10001 copilot

USER copilot

EXPOSE 8100

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]