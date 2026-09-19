FROM python:3.14-slim

ENV DOCKER=1

WORKDIR /app

COPY poetry.lock pyproject.toml ./

RUN pip install poetry
RUN poetry install --no-root --only main

#install chromium browser for playwright
#this is for screenshots
RUN playwright install chromium && \
    playwright install-deps chromium

COPY *.py .

CMD ["python", "-u", "bluesky-youtube-mirror.py"]