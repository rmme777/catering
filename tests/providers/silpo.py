import random
import time
import uuid
from typing import Literal

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

OrderStatus = Literal["not started", "cooking", "cooked", "finished"]

STORAGE: dict[str, OrderStatus] = {}
"""
{
    "fcc5ed76-ea30-46d8-83db-fb4b0bfbaa03": "not started"
}
"""


app = FastAPI(title="Silpo API")


class OrderItem(BaseModel):
    dish: str
    quantity: int


class OrderRequestBody(BaseModel):
    order: list[OrderItem]


def update_order_status(order_id: str):
    ORDER_STATUSES: tuple[OrderStatus, ...] = ("cooking", "cooked", "finished")
    for status in ORDER_STATUSES:
        time.sleep(random.randint(4, 6))
        STORAGE[order_id] = status
        print(f"SILPO: [{order_id}] --> {status}")


@app.post("/api/orders")
def make_order(body: OrderRequestBody, background_tasks: BackgroundTasks):
    print(body)

    order_id = str(uuid.uuid4())
    STORAGE[order_id] = "not started"
    background_tasks.add_task(update_order_status, order_id)

    return {"id": order_id, "status": "not started"}


@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    return {"id": order_id, "status": STORAGE.get(order_id)}