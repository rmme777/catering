from rest_framework import viewsets, serializers, routers, permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Restaurant, Dish, OrderItem, OrderStatus, Order
from users.models import User

class DishSerializer(serializers.ModelSerializer):
    exclude = ["restaurant"]

    class Meta:
        model = Dish

class RestaurantSerializer(serializers.ModelSerializer):
    dishes = DishSerializer(many=True)

    class Meta:
        model = Restaurant
        fields ="__all__"

class OrderItemSerializer(serializers.Serializer):
    dish = serializers.PrimaryKeyRelatedField(queryset=Dish.objects.all())
    quantity = serializers.IntegerField(min_value=1, max_value=20)

class OrderSerializer(serializers.Serializer):
    items = OrderItemSerializer(many=True)
    eta = serializers.DateField
    total = serializers.IntegerField(min_value=1, read_only=True)
    status = serializers.ChoiceField(OrderStatus.choices(), read_only=True)

class FoodAPIViewSet(viewsets.GenericViewSet):

    def get_permissions(self):
        if self.action == "dishes":
            return [permissions.AllowAny()]
        elif self.action == "create_order":
            return [permissions.IsAuthenticated()]
        elif self.action == "get_orders":
            return [permissions.IsAuthenticated]
        elif self.action == "create_dish":
            return [permissions.IsAdminUser]

    @action(methods=["get"], detail=False)
    def dishes(self, request: Request) -> Response:
        restaurants = Restaurant.objects.all()
        serializer = RestaurantSerializer(restaurants, many=True)
        return Response(data=serializer.data)

    @action(methods=["post"], detail=False, url_path=r"orders")
    def create_order(self, request: Request) -> Response:

        serializer = OrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = Order.objects.create(
            status=OrderStatus.NOT_STARTED,
            user=request.user,
            delivery_provider="uklon",
            eta=serializer.validated_data["eta"]
        )

        items = serializer.validated_data["items"]

        for dish_order in items:
            instance = OrderItem.objects.create(
                dish=dish_order["dish"],
                quantity=dish_order["quantity"],
                order=order
            )
            print(f"New Dish Order Item is created: {instance.pk}")

        print(f"New Food Order is created: {order.pk}. ETA: {order.eta}")
        return Response(data={
            "id": order.pk,
            "status": order.status,
            "eta": order.eta,
            "total": order.total
        }, status=201)

    @action(method=["post"], detail=False, url_path=r"dishes")
    def create_dish(self, request: Request):

        serializer = DishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dish = Dish.objects.create(
            name=serializer.validated_data["name"],
            price=serializer.validated_data["price"],
            restaurant=serializer.validated_data["restaurant"]
        )
        return Response(data={
            "id": dish.pk,
            "name": dish.name,
            "price": dish.price,
            "restaurant": dish.restaurant
        }, status=201)

    @action(methods=["get"], detail=False, url_path=r"orders/(?P<id>\d+)")
    def get_orders(self, request: Request) -> Response:
        order = Order.objects.get(id=id)
        serializer = OrderSerializer(order)
        return Response(data=serializer.data)

router = routers.DefaultRouter()
router.register(
    prefix="",
    viewset=FoodAPIViewSet,
    basename="food"
)