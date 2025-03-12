FROM python:3.12

ENV PYTHONUNBUFFERED=1
RUN mkdir app
COPY . /app
RUN pip install --no-cache-dir /app

CMD [ "python", "/app/src/start_aws_gha_runner/" ]
