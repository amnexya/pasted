FROM alpine:latest

WORKDIR .

RUN apk add python3 py3-pip build-base python3-dev libffi-dev

COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir --break-system-packages

COPY app ./app
COPY pasted ./pasted

CMD ["sh", "-c", "./pasted --port ${PORT} --host ${HOST}"]