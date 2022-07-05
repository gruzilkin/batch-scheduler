from datetime import datetime
import os, json, asyncio, random, time
import aio_pika
import psycopg2

async def get_queue_connection():
    host = os.environ['RABBITMQ_HOST']
    user = os.environ['RABBITMQ_USER']
    password = os.environ['RABBITMQ_PASS']

    return await aio_pika.connect(host=host, login=user, password=password)

def create_db_connection():
    dbname = os.environ['DB_NAME']
    user = os.environ['DB_USER']
    password = os.environ['DB_PASSWORD']
    host = os.environ['DB_HOST']
    return psycopg2.connect(dbname=dbname, user=user, password=password, host=host)

async def listen_rabbit_messages():
    with create_db_connection() as db_connection:
        connection = await get_queue_connection()
        async with connection:
            channel = await connection.channel()
            async with channel:
                await channel.set_qos(prefetch_count=1)
                queue = await channel.declare_queue("worker", auto_delete=False)
                await queue.bind("amq.topic", "subtask.created")
                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        async with message.process(requeue = True):
                            id = json.loads(message.body)
                            print(f"Received message {id} of type {type(id)}")
                            process_message(db_connection, id)

def process_message(db_connection, id):
    if random.random() < 0.1:
        raise Exception("worker crashed")
    
    start = datetime.now()
    time.sleep(random.uniform(1,2))
    end = datetime.now()

    with db_connection.cursor() as cursor:
        cursor.execute(f""" UPDATE sub_task
                            SET start_time = %s, end_time = %s
                            WHERE id = %s""", (start, end, id,))
    db_connection.commit()



async def main():
    try:
        coros = [listen_rabbit_messages()]
        tasks = [asyncio.create_task(coro) for coro in coros]
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

asyncio.run(main())