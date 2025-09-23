import uuid

from django.core.mail import send_mail

from config import celery_app
from shared.cache import CacheService

from .models import User


@celery_app.task(queue="default")
def send_user_activation_email(email: str, activation_key: str):
    # SMTP Client Send Email Request
    activation_link = f"http://127.0.0.1:8000/users/activate/{activation_key}"
    send_mail(
        subject="User Activation",
        message=f"Please, activate your account: {activation_link}",
        from_email="admin@catering.com",
        recipient_list=[email],
    )


class ActivationService:
    UUID_NAMESPACE = uuid.uuid4()

    def __init__(self):
        self.cache: CacheService = CacheService()

    @staticmethod
    def create_activation_key():
        # whether:
        # key = uuid.uuid3(self.UUID_NAMESPACE, self.email)
        # or
        return uuid.uuid4()

    def save_activation_information(self, user_id: int, activation_key: str):
        """Save activation data to the cache.
        1. Connect to the Cache Service
        2. Save structure to the Cache:
        {
            "0a33d01f-b18f-4369-abd2-e85002f24846": {
                "user_id": 3
            }
        }
        3. Return `None`
        """

        self.cache.set(
            namespace="activation",
            key=activation_key,
            value={"user_id": user_id},
            ttl=3000,
        )

        return None

    def activate_user(self, activation_key: str) -> User | bool:
        user_cache_payload: dict | None = self.cache.get(
            namespace="activation",
            key=activation_key,
        )

        if user_cache_payload is None:
            return False

        user = User.objects.get(id=user_cache_payload["user_id"])
        if not user.is_active:
            user.is_active = True
            user.save()

        self.cache.delete("activation", activation_key)
        return user
