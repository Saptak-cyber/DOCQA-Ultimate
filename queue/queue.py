import json
import redis
import uuid

r = redis.Redis.from_url("redis://localhost:6379/0")

QUEUE_KEY = "pdf_tasks"

def enqueue_task(document_id, user_id, step):
    task = {
        "task_id": str(uuid.uuid4()),
        "document_id": document_id,
        "user_id": user_id,
        "step": step
    }
    r.lpush(QUEUE_KEY, json.dumps(task))
    return task["task_id"]

def dequeue_task():
    data = r.brpop(QUEUE_KEY)
    return json.loads(data[1])
