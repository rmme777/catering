from django.contrib import admin
from django.urls import path, include
from users.views import router as users_router
from food.views import router as food_router, import_dishes
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    path("admin/food/dish/import-dishes/", import_dishes, name="import_dishes"),
    path("admin/", admin.site.urls),
    path("users/", include(users_router.urls)),
    path("food/", include(food_router.urls))
    ] + static(settings.STATIC_URL, documendockert_root=settings.STATIC_ROOT)