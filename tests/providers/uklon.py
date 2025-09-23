import asyncio
import random
import uuid

import httpx
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel, Field

CATERING_API_WEBHOOK_URL = "http://api:8000/webhook/uklon/3392cc8d-843f-4999-aa72-f914072f7f69/"

ORDER_STATUSES = ("not started", "delivery", "delivered")
STORAGE: dict[str, dict] = {}

app = FastAPI()


class OrderRequestBody(BaseModel):
    addresses: list[str] = Field(min_length=1)
    comments: list[str] = Field(min_length=1)


async def delivery(order_id: str):
    for _ in range(5):
        STORAGE[order_id]["location"] = (random.random(), random.random())

    for address in STORAGE[order_id]["addresses"]:
        await asyncio.sleep(1)
        for _ in range(5):
            STORAGE[order_id]["location"] = (random.random(), random.random())
            await asyncio.sleep(0.5)

        print(f"🏁 Delivered to {address}")


async def update_order_status(order_id):
    for status in ORDER_STATUSES[1:]:
        STORAGE[order_id]["location"] = (random.random(), random.random())
        await asyncio.sleep(random.randint(1, 2))

        STORAGE[order_id]["status"] = status
        print(f"UKLON: [{order_id}] --> {status}")

        # уведомляем твой API о смене статуса
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    CATERING_API_WEBHOOK_URL,
                    data={"id": order_id, "status": status, "location": STORAGE[order_id]["location"]},
                )
            except httpx.ConnectError:
                print("API connection failed")
            else:
                print(f"UKLON: notified catering API about {status}")


@app.post("/drivers/orders")
def make_order(body: OrderRequestBody, background_tasks: BackgroundTasks):
    print(body)
    order_id = str(uuid.uuid4())
    STORAGE[order_id] = {
        "id": order_id,
        "status": "not started",
        "addresses": body.addresses,
        "comments": body.comments,
        "location": (random.random(), random.random()),
    }
    background_tasks.add_task(update_order_status, order_id)

    return STORAGE.get(order_id, {"error": "No such order"})


@app.get("/drivers/orders/{order_id}")
def get_order(order_id: str):
    return STORAGE.get(order_id, {"error": "Nu such order"})
