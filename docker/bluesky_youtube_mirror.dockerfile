FROM python:3.14-slim

ENV DOCKER=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY *.py .

CMD ["python", "-u", "bluesky-youtube-mirror.py"]