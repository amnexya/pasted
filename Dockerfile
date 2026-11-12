FROM alpine:latest

WORKDIR /app

RUN apk add python3 py3-pip build-base python3-dev libffi-dev libmagic

COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir --break-system-packages

COPY app ./app
COPY pasted ./pasted

ENV FLASK_APP=app

CMD ["sh", "-c", "flask db init && flask db migrate && flask db upgrade && exec ./pasted --port ${PORT} --host ${HOST}"]