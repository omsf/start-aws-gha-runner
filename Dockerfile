FROM python:3.12-alpine

ENV PYTHONUNBUFFERED=1
RUN apk add --no-cache git openssh-client
RUN mkdir app
COPY . /app
RUN pip install --no-cache-dir /app

CMD [ "python", "/app/src/start_aws_gha_runner/" ]
