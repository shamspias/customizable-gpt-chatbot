from rest_framework import serializers

from ausers.models import User, Customer
from common.serializers import ThumbnailerJSONSerializer


class UserSerializer(serializers.ModelSerializer):
    profile_picture = ThumbnailerJSONSerializer(required=False, allow_null=True, alias_target='users')

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'first_name',
            'last_name',
            'phone_number',
            'profile_picture',
        )
        read_only_fields = ('username', 'email',)


class CreateUserSerializer(serializers.ModelSerializer):
    profile_picture = ThumbnailerJSONSerializer(required=False, allow_null=True, alias_target='users')
    sex = serializers.CharField(max_length=15, allow_blank=True, required=False)
    tokens = serializers.SerializerMethodField()

    def get_tokens(self, user):
        return user.get_tokens()

    def create(self, validated_data):
        # call create_user on user object. Without this
        # the password will be stored in plain text.
        user = User.objects.create_user(**validated_data)

        # Create customer temporary until use signal
        Customer.objects.create(user=user, sex=validated_data['sex'])

        return user

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'phone_number',
            'password',
            'first_name',
            'last_name',
            'sex',
            'tokens',
            'profile_picture',
        )
        read_only_fields = ('tokens',)
        extra_kwargs = {'password': {'write_only': True}}


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            'id',
            'date_of_birth',
            'sex'
        )
