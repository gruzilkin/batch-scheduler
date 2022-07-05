CREATE TABLE task (
    id SERIAL PRIMARY KEY,
    name varchar(32) NOT NULL,
    start_time timestamp with time zone NOT NULL,
    last_scheduled_time timestamp with time zone DEFAULT TIMESTAMP 'epoch',
    end_time timestamp with time zone NOT NULL,
    interval integer not null
);

CREATE TABLE sub_task (
    id SERIAL PRIMARY KEY,
    task_id integer REFERENCES task(id) ON DELETE CASCADE,
    scheduled_time timestamp with time zone NOT NULL,
    start_time timestamp with time zone,
    end_time timestamp with time zone
);