"""
RESTAURANT: {
    EXTERNAL STATUS: INTERNAL STATUS
}
"""

from .enums import OrderStatus
from .providers import kfc, silpo, uklon

RESTAURANT_EXTERNAL_TO_INTERNAL: dict[str, dict[str, OrderStatus]] = {
    "silpo": {
        silpo.OrderStatus.NOT_STARTED: OrderStatus.NOT_STARTED,
        silpo.OrderStatus.COOKING: OrderStatus.COOKING,
        silpo.OrderStatus.COOKED: OrderStatus.COOKED,
    },
    "kfc": {
        kfc.OrderStatus.NOT_STARTED: OrderStatus.NOT_STARTED,
        kfc.OrderStatus.COOKING: OrderStatus.COOKING,
        kfc.OrderStatus.COOKED: OrderStatus.COOKED,
    },
}

PROVIDER_EXTERNAL_TO_INTERNAL: dict[str, dict[str, OrderStatus]] = {
    "uklon": {uklon.OrderStatus.NOT_STARTED: OrderStatus.NOT_STARTED,
              uklon.OrderStatus.DELIVERY: OrderStatus.DELIVERY,
              uklon.OrderStatus.DELIVERED: OrderStatus.DELIVERED}
}