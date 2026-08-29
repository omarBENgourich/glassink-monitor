FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# No third-party dependencies on purpose: http.server, urllib and smtplib cover
# every channel here. One less thing to keep patched on a plant network.
COPY src/ ./src/

RUN useradd --create-home --uid 10003 notify
USER notify

EXPOSE 8080
CMD ["python", "-m", "src.main"]
