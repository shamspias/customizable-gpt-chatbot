from django.urls import path
from .views import TrainView

urlpatterns = [
    path('train/<int:object_id>/', TrainView.as_view(), name='train_view'),
]
