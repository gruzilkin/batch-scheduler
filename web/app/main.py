import os, json
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

import psycopg2

import aio_pika

class Task(BaseModel):
    name: str
    start: datetime
    end: datetime
    interval: int

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

def create_db_connection():
    dbname = os.environ['DB_NAME']
    user = os.environ['DB_USER']
    password = os.environ['DB_PASSWORD']
    host = os.environ['DB_HOST']
    return psycopg2.connect(dbname=dbname, user=user, password=password, host=host)

async def sender(message):
    host = os.environ['RABBITMQ_HOST']
    user = os.environ['RABBITMQ_USER']
    password = os.environ['RABBITMQ_PASS']

    connection =  await aio_pika.connect(host=host, login=user, password=password)
    async with connection:
        channel = await connection.channel()
        async with channel:
            topic = await channel.get_exchange("amq.topic")
            await topic.publish(
                aio_pika.Message(body=json.dumps(message).encode()),
                routing_key=f"task.created")

@app.post("/task/")
async def create_item(task: Task):
    with create_db_connection() as connection:
        with connection.cursor() as cur:
            sql_args = (task.name, task.start, task.end, task.interval)
            cur.execute(f"INSERT INTO task (name, start_time, end_time, interval) VALUES ({','.join(['%s'] * len(sql_args))})", sql_args)
            connection.commit()
    await sender("new task")
    return task