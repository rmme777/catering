from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from food.views import import_dishes, kfc_webhook
from food.views import router as food_router
from food.views import uklon_webhook
from users.views import router as users_router

urlpatterns = [
    path("admin/food/dish/import-dishes/", import_dishes, name="import_dishes"),
    path("admin/", admin.site.urls),
    path("users/", include(users_router.urls)),
    path("food/", include(food_router.urls)),
    path("webhook/kfc/ba407b9e-5c23-4726-8ad9-28c084b6ee8d/", kfc_webhook),
    path("webhook/uklon/3392cc8d-843f-4999-aa72-f914072f7f69/", uklon_webhook),
] + static(settings.STATIC_URL, documendockert_root=settings.STATIC_ROOT)
