from rest_framework import viewsets, serializers, routers, permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Restaurant, Dish, OrderItem, OrderStatus, Order, DeliveryProvider
from django.db import transaction
from rest_framework.exceptions import ValidationError
from django.shortcuts import redirect
import csv
import io

from rest_framework.pagination import LimitOffsetPagination
from rest_framework.pagination import PageNumberPagination
from django.contrib.admin.views.decorators import staff_member_required

from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

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
    delivery_provider = serializers.CharField()

class BaseFilters:
    @staticmethod
    def camel_to_snake_case(value):
        result = []
        for char in value:
            if char.isupper():
                if result:
                    result.append("_")
                result.append(char.lower())
            else:
                result.append(char)
        return "".join(result)

    @staticmethod
    def snake_to_camel_case(value):
        parts = value.split("_")
        return parts[0] + "".join(word.capitalize() for word in parts[1:])

    def __init__(self, **kwargs) -> None:
        errors: dict[str, dict[str]] = {"queryParams": {}}

        for key, value in kwargs.items():
            _key: str = self.camel_to_snake_case(key)

            try:
                extractor = getattr(self, f"extract_{_key}")
            except AttributeError:
                errors["queryParams"][
                    key
                ] = f"You forgot to define `extract_{_key}` method in your class `{self.__class__.__name__}`"
                raise ValidationError(errors)

            try:
                _extracted_value = extractor(value)
            except ValidationError as error:
                errors["queryParams"][key] = str(error)
            else:
                setattr(self, _key, _extracted_value)

        if errors["queryParams"]:
            raise ValidationError(errors)


class FoodFilters(BaseFilters):

    def extract_delivery_provider(
        self, provider: str | None = None
    ) -> DeliveryProvider | None:
        if provider is None:
            return None
        else:
            provider_name = provider.upper()
            try:
                _provider = DeliveryProvider[provider_name]
            except KeyError:
                raise ValidationError(f"Provider {provider} is not supported")
            else:
                return _provider

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

    @method_decorator(cache_page(10))
    @action(methods=["get"], detail=False)
    def dishes(self, request: Request) -> Response:
        filters = FoodFilters(**request.query_params.dict())
        restaurants = (
            Dish.objects.all()
            if filters.name is None
            else Dish.objects.filter(name__icontains=filters.name)
        )

        paginator = LimitOffsetPagination()
        page = paginator.paginate_queryset(restaurants, request, view=self)

        if page is not None:
            serializer = OrderSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = RestaurantSerializer(restaurants, many=True)
        return Response(data=serializer.data)

    @transaction.atomic
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

    @action(methods=["post"], detail=False, url_path=r"dishes")
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

    @action(methods=["get"], detail=False, url_path=r"orders")
    def all_orders(self, request: Request) -> Response:
        # filters = FoodFilters(**request.query_params.dict())
        # status: str | None = request.query_params.get("status")
        # orders = (
        #     Order.objects.all()
        #     if filters.delivery_provider is None
        #     else Order.objects.filter(delivery_provider=filters.delivery_provider)
        # )

        orders = Order.objects.all()

        paginator = PageNumberPagination()
        paginator.page_size = 2
        paginator.page_size_query_param = "size"
        page = paginator.paginate_queryset(orders, request, view=self)

        if page is not None:
            serializer = OrderSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)


@staff_member_required
def import_dishes(request):
    if request.method != "POST":
        raise ValueError(f"Method {request.method} is not allowed on this resource")

    csv_file = request.FILES.get("file")
    if csv_file is None:
        raise ValueError("No CSV File Provided")

    decoded = csv_file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))
    total = 0

    for row in reader:
        restaurant_name = row["restaurant"]
        try:
            rest = Restaurant.objects.get(name__icontains=restaurant_name.lower())
        except Restaurant.DoesNotExist:
            print(f"Skipping restaurant {restaurant_name}")
        else:
            print(f"Restaurant {rest} found")

        Dish.objects.create(name=row["name"], price=int(row["price"]), restaurant=rest)
        total += 1

    print(f"{total} dishes uploaded to the database")

    return redirect(request.META.get("HTTP_REFERER", "/"))


router = routers.DefaultRouter()
router.register(
    prefix="",
    viewset=FoodAPIViewSet,
    basename="food"
)