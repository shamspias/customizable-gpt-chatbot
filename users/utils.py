def jwt_response_payload_handler(token, user=None, request=None):
    """
    Custom JWT response payload handler.
    """
    return {
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        },
    }
