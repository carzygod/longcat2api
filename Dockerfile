FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY longcat2api/ longcat2api/

ENV LONGCAT_HOST=0.0.0.0
ENV LONGCAT_PORT=9090
ENV LONGCAT_DATA_DIR=/app/data
ENV LONGCAT_BROWSER_DATA=/app/data/browser
ENV LONGCAT_SESSION_FILE=/app/data/longcat_session.json

EXPOSE 9090

CMD ["python", "-m", "longcat2api"]

