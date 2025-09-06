from rest_framework.exceptions import ValidationError
from rest_framework import permissions, routers, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from typing import Any
from django.contrib.auth.hashers import make_password, check_password
from rest_framework import serializers
from .models import User
from .services import ActivationService
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone_number",
            "first_name",
            "last_name",
            "password",
            "role",
        ]

    def validate(self, attrs: dict[str, Any]):
        """Change the password for its hash to make Token-based authentication available."""

        attrs["password"] = make_password(attrs["password"])

        return super().validate(attrs=attrs)

class UserActivationSerializer(serializers.Serializer):
    key = serializers.UUIDField()



class UsersAPIViewSet(viewsets.GenericViewSet):
    authentication_classes = [JWTAuthentication]
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]
        elif self.action == "activate":
            return [permissions.AllowAny()]
        elif self.action == "reactivate":
            return {permissions.AllowAny()}
        else:
            return [permissions.IsAuthenticated()]

    @staticmethod
    def list(request: Request):
        return Response(UserSerializer(request.user).data, status=200)

    @staticmethod
    def create(request: Request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        activation_service = ActivationService(email=getattr(serializer.instance, "email"))

        activation_key = activation_service.create_activation_key()
        activation_service.save_activation_information(
            user_id=getattr(serializer.instance, "id"),
            activation_key=activation_key
        )
        activation_service.send_user_activation_email(activation_key=activation_key)

        return Response(UserSerializer(serializer.instance).data, status=201)

    @action(methods=["GET"], detail=False, url_path=r"activate/(?P<key>[0-9a-f-]+)")
    def activate(self, request: Request, key: str = None):
        if key is None:
            raise ValidationError("Activation key is required")

        activation_service = ActivationService()
        try:
            user = activation_service.activate_user(activation_key=key)
        except ValueError:
            raise ValidationError("Activation link expired")

        if not user:
            return Response({"detail": "Activation is not available. Please use http://127.0.0.1:8000/users/reactivate."},
                            status=404)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=200
        )

    @action(methods=["POST"], detail=False, url_path="reactivate")
    def reactivate(self, request: Request):
        email = request.data.get("email")
        raw_password = request.data.get("password")
        user = get_object_or_404(User, email=email)

        if user.is_active:
            return Response(
                {"detail": "User already activated"}, status=403)

        if not check_password(raw_password, user.password):
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST
            )

        activation_service = ActivationService(email=email)
        activation_key = activation_service.create_activation_key()
        activation_service.save_activation_information(
            user_id=user.id,
            activation_key=activation_key
        )
        activation_service.send_user_activation_email(activation_key=activation_key)

        return Response({"message": "Activation email sent"}, status=200)


router = routers.DefaultRouter()
router.register(r"", UsersAPIViewSet, basename="user")
