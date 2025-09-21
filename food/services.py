from dataclasses import asdict, dataclass, field
from time import sleep

from django.db.models import QuerySet

from config import celery_app
from shared.cache import CacheService

from .enums import OrderStatus
from .mapper import RESTAURANT_EXTERNAL_TO_INTERNAL, PROVIDER_EXTERNAL_TO_INTERNAL
from .models import Order, OrderItem, Restaurant
from .providers import kfc, silpo, uklon

ORDER_LIFE_TIME = 604800

@dataclass
class TrackingOrder:
    """
    {
        17: {  // internal Order.id
            restaurants: {
                1: {  // internal restaurant id
                    status: NOT_STARTED, // internal
                    external_id: 13,
                    request_body: {...},
                },
                2: {  // internal restaurant id
                    status: NOT_STARTED, // internal
                    external_id: edf055b8-06e8-40ed-ab35-300fef3e0a5d,
                    request_body: {...},
                },
            },
            delivery: {
                location: (..., ...),
                status: NOT STARTED, DELIVERY, DELIVERED
            }
        },
        18: ...
    }
    """

    restaurants: dict = field(default_factory=dict)
    delivery: dict = field(default_factory=dict)


def all_orders_cooked(order_id: int):
    cache = CacheService()
    tracking_order = TrackingOrder(**cache.get(namespace="orders", key=str(order_id)))
    print(f"Checking if al lorders are cooked: {tracking_order.restaurants}")

    if all((payload["status"] == OrderStatus.COOKED for _, payload in tracking_order.restaurants.items())):
        Order.objects.filter(id=order_id).update(status=OrderStatus.COOKED)
        print("✅ All orders are COOKED")

        # Start orders delivery
        order_delivery.delay(order_id)
    else:
        print(f"Not all orders are cooked: {tracking_order=}")

@celery_app.task(queue="default")
def order_delivery(order_id: int):
    """Using random provider (or now only Uklon) - start processing delivery order."""

    print("🚚 DELIVERY PROCESSING STARTED")

    provider = uklon.Client()
    cache = CacheService()
    order = Order.objects.get(id=order_id)

    def get_internal_status(status: uklon.OrderStatus) -> OrderStatus:
        return PROVIDER_EXTERNAL_TO_INTERNAL["uklon"][status]

    # update Order state
    order.status = OrderStatus.DELIVERY_LOOKUP
    order.save()

    # prepare data for the first request
    addresses: list[str] = []
    comments: list[str] = []

    for rest_name, address in order.delivery_meta():
        addresses.append(address)
        comments.append(f"Delivery to the {rest_name}")

    # создаём заказ во внешнем провайдере
    response: uklon.OrderResponse = provider.create_order(
        uklon.OrderRequestBody(addresses=addresses, comments=comments)
    )

    # сохраняем mapping external_id -> internal order_id
    cache.set(
        namespace="uklon_orders",
        key=response.id,
        value={"internal_order_id": order_id},
    )

    # обновляем кеш TrackingOrder (без проставления DELIVERED!)
    tracking_order = TrackingOrder(**cache.get("orders", str(order.pk)))
    tracking_order.delivery["status"] = get_internal_status(response.status)
    tracking_order.delivery["location"] = response.location
    cache.set("orders", str(order_id), asdict(tracking_order))

    print(f"🏁 UKLON order created [{response.id}] status={response.status} 📍 {response.location}")

@celery_app.task(queue="default")
def order_in_silpo(order_id: int, items: QuerySet[OrderItem]):
    """Short polling requests to the Silpo API

    NOTES
    get order from cache
    is external_id?
      no: make order
      yes: get order
    """

    client = silpo.Client()
    cache = CacheService()
    restaurant = Restaurant.objects.get(name="silpo")

    def get_internal_status(status: silpo.OrderStatus) -> OrderStatus:
        return RESTAURANT_EXTERNAL_TO_INTERNAL["silpo"][status]

    cooked = False
    while not cooked:
        sleep(1)  # just a delay

        # GET ITEM FROM THE CACHE
        cached_data = cache.get(namespace="orders", key=str(order_id)) or {}
        tracking_order = TrackingOrder(
            restaurants={
                str(order_id): {
                    "status": cached_data.get("status"),
                    "external_id": cached_data.get("external_id"),
                }
            }
        )
        # validate
        silpo_order = tracking_order.restaurants.get(str(restaurant.pk))
        if not silpo_order:
            raise ValueError("No Silpo in orders processing")

        # PRINT CURRENT STATUS
        print(f"CURRENT SILPO ORDER STATUS: {silpo_order['status']}")

        if not silpo_order["external_id"]:
            # ✨ MAKE THE FIRST REQUEST IF NOT STARTED
            response: silpo.OrderResponse = client.create_order(
                    silpo.OrderRequestBody(
                        order=[
                            silpo.OrderItem(dish=item.dish.name, quantity=item.quantity)
                            for item in items
                        ]
                    )
                )

            internal_status: OrderStatus = get_internal_status(response.status)

            # UPDATE CACHE WITH EXTERNAL ID AND STATE
            tracking_order.restaurants[str(restaurant.pk)] |= {
                "external_id": response.id,
                "status": internal_status,
            }
            cache.set(
                namespace="orders", key=str(order_id), value=asdict(tracking_order), ttl=ORDER_LIFE_TIME
            )
        else:
            # ✨ IF ALREADY HAVE EXTERNAL ID - JUST RETRIEVE THE ORDER
            # PASS EXTERNAL SILPO ORDER ID
            response = client.get_order(silpo_order["external_id"])
            internal_status = get_internal_status(response.status)

            print(
                f"Tracking for Silpo Order with HTTP GET /api/order. Status: {internal_status}"
            )

            if silpo_order["status"] != internal_status:  # STATUS HAS CHANGED
                tracking_order.restaurants[str(restaurant.pk)][
                    "status"
                ] = internal_status
                print(f"Silpo order status changed to {internal_status}")
                cache.set(
                    namespace="orders", key=str(order_id), value=asdict(tracking_order), ttl=ORDER_LIFE_TIME
                )
                # if started cooking?
                if internal_status == OrderStatus.COOKING:
                    Order.objects.filter(id=order_id).update(status=OrderStatus.COOKING)

            if internal_status == OrderStatus.COOKED:
                cooked = True
                all_orders_cooked(order_id)


@celery_app.task(queue="high_priority")
def order_in_kfc(order_id: int, items):
    client = kfc.Client()
    cache = CacheService()
    restaurant = Restaurant.objects.get(name="kfc")

    def get_internal_status(status: kfc.OrderStatus) -> OrderStatus:
        return RESTAURANT_EXTERNAL_TO_INTERNAL["kfc"][status]

    # GET TRACKING ORDER FROM THE CACHE
    tracking_order = TrackingOrder(**cache.get(namespace="orders", key=str(order_id)))

    response: kfc.OrderResponse = client.create_order(
        kfc.OrderRequestBody(order=[kfc.OrderItem(dish=item.dish.name, quantity=item.quantity) for item in items])
    )
    internal_status = get_internal_status(response.status)

    # UPDATE CACHE WITH EXTERNAL ID AND STATE
    tracking_order.restaurants[str(restaurant.pk)] |= {
        "external_id": response.id,
        "status": internal_status,
    }

    print(f"Created KFC Order. External ID: {response.id} Status: {internal_status}")
    cache.set(namespace="orders", key=str(order_id), value=asdict(tracking_order), ttl=ORDER_LIFE_TIME)

    # save another item form Mapping to the Internal Order
    cache.set(
        namespace="kfc_orders",
        key=response.id,  # external KFC order id
        value={
            "internal_order_id": order_id,
        },
    )

    # 🚧 CHECK IF ALL ORDERS ARE COOKED
    if all_orders_cooked(order_id):
        cache.set(namespace="orders", key=str(order_id), value=asdict(tracking_order), ttl=ORDER_LIFE_TIME)
        Order.objects.filter(id=order_id).update(status=OrderStatus.COOKED)



def schedule_order(order: Order):
    # define services and data state
    cache = CacheService()
    tracking_order = TrackingOrder()

    items_by_restaurants = order.items_by_restaurant()
    for restaurant, items in items_by_restaurants.items():
        # update tracking order instance to be saved to the cache
        tracking_order.restaurants[str(restaurant.pk)] = {
            "external_id": None,
            "status": OrderStatus.NOT_STARTED,
        }

    # update cache insatnce only once in the end
    cache.set(namespace="orders", key=str(order.pk), value=asdict(tracking_order), ttl=ORDER_LIFE_TIME)

    # start processing after cache is complete
    for restaurant, items in items_by_restaurants.items():
        match restaurant.name.lower():
            case "silpo":
                print(f"Sending order_in_silpo for order_id={order.pk} with {len(items)} items")
                order_in_silpo.delay(order.pk, items)
                # or
                # order_in_silpo.apply_async()
            case "kfc":
                order_in_kfc.delay(order.pk, items)
            case _:
                raise ValueError(
                    f"Restaurant {restaurant.name} is not available for processing"
                )

