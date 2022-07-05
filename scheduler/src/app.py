import os, json, asyncio, sys
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

async def listen_rabbit_messages(task_queue: asyncio.Queue):
    connection = await get_queue_connection()
    async with connection:
        channel = await connection.channel()
        async with channel:
            await channel.set_qos(prefetch_count=1)
            queue = await channel.declare_queue("scheduler", auto_delete=False)
            await queue.bind("amq.topic", "task.created")

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        await task_queue.put("wake up, neo!")

async def send_rabbit_messages(sub_task_queue: asyncio.Queue):
    connection = await get_queue_connection()
    async with connection:
        channel = await connection.channel()
        async with channel:
            topic = await channel.get_exchange("amq.topic")
            while True:
                id = await sub_task_queue.get()
                await topic.publish(
                    aio_pika.Message(body=json.dumps(id).encode()),
                    routing_key=f"subtask.created")
                print(f"subtask created: {id}")

async def sql_stuff(task_queue: asyncio.Queue, sub_task_queue: asyncio.Queue):
    with create_db_connection() as connection:
        while True:
            sub_task_ids = []
            time_to_sleep = sys.float_info.max

            with connection.cursor() as cursor:
                cursor.execute(f""" SELECT id
                                    FROM task
                                    WHERE last_scheduled_time + make_interval(secs => interval) < now()""")
                task_ids = [row[0] for row in cursor.fetchall()]

                if task_ids:
                    for task_id in task_ids:
                        cursor.execute(f""" INSERT INTO sub_task (task_id, scheduled_time)
                                            VALUES (%s, now())
                                            RETURNING id""", (task_id,))
                        (sub_task_id,) = cursor.fetchone()
                        sub_task_ids.append(sub_task_id)
                    
                    cursor.execute(f""" UPDATE task
                                        SET last_scheduled_time = now()
                                        WHERE id IN ({','.join(['%s'] * len(task_ids))})""", task_ids)

                    cursor.execute(f""" SELECT MIN (EXTRACT (EPOCH FROM last_scheduled_time + make_interval(secs => interval) - now()))
                                        FROM task;""")
                    (time_to_sleep,) = cursor.fetchone()
                    print(time_to_sleep)

            connection.commit()
        
            for sub_task_id in sub_task_ids:
                await sub_task_queue.put(sub_task_id)

            wait_for_signal_task = asyncio.create_task(task_queue.get())
            done, pending = await asyncio.wait([wait_for_signal_task], timeout=float(time_to_sleep))
            for task in pending:
                    task.cancel()

async def main():
    try:
        task_queue = asyncio.Queue()
        sub_task_queue = asyncio.Queue()
        coros = [listen_rabbit_messages(task_queue), sql_stuff(task_queue, sub_task_queue), send_rabbit_messages(sub_task_queue)]
        tasks = [asyncio.create_task(coro) for coro in coros]
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

asyncio.run(main())