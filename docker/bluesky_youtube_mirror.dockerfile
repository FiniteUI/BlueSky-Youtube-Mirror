FROM python:3.14-slim

ENV DOCKER=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

#install chromium browser for playwright
#this is for screenshots
RUN playwright install chromium && \
    playwright install-deps chromium

COPY *.py .

CMD ["python", "-u", "bluesky-youtube-mirror.py"]