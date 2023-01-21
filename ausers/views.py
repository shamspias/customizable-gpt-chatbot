from rest_framework import viewsets, mixins
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from ausers.models import User, Customer
from ausers.permissions import IsUserOrReadOnly
from ausers.serializers import (
    CreateUserSerializer,
    UserSerializer,
    CustomerSerializer,
)


class UserViewSet(mixins.UpdateModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Creates, Updates and Retrieves - User Accounts
    """

    queryset = User.objects.all()
    serializers = {'default': UserSerializer, 'create': CreateUserSerializer}
    permissions = {'default': (IsUserOrReadOnly,), 'create': (AllowAny,)}

    def get_serializer_class(self):
        return self.serializers.get(self.action, self.serializers['default'])

    def get_permissions(self):
        self.permission_classes = self.permissions.get(self.action, self.permissions['default'])
        return super().get_permissions()

    @action(detail=False, methods=['get'], url_path='info', url_name='info')
    def get_user_data(self, instance):
        try:
            return Response(UserSerializer(self.request.user, context={'request': self.request}).data,
                            status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Wrong auth token' + str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CustomerViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for customers
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsUserOrReadOnly, IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='info', url_name='info')
    def get_user_data(self, instance):
        try:
            customer_obj = Customer.objects.get(user__email__exact=self.request.user)
            return Response(CustomerSerializer(customer_obj, context={'request': self.request}).data,
                            status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Wrong auth token' + str(e)}, status=status.HTTP_400_BAD_REQUEST)
