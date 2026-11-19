FROM python:3.14-slim

ENV DOCKER=1

WORKDIR /app

COPY poetry.lock pyproject.toml ./

RUN pip install poetry
RUN poetry install --no-root --only main

#install chromium browser for playwright
#this is for screenshots
RUN poetry run playwright install chromium && \
    poetry run playwright install-deps chromium

COPY *.py .

CMD ["poetry", "run", "python", "-u", "bluesky-youtube-mirror.py"]