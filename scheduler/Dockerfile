# syntax=docker/dockerfile:1

FROM python:3.9

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY wait-for-it.sh .
RUN chmod a+x wait-for-it.sh

COPY ./src/ .

EXPOSE 5678

CMD ./wait-for-it.sh -t 600 $RABBITMQ_HOST:5672 && ./wait-for-it.sh -t 600 $DB_HOST:5432 && python3 -m debugpy --listen 0.0.0.0:5678 app.py