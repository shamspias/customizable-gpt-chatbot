from django.urls import path
from . import views

urlpatterns = [
    path('train/<int:object_id>/', views.train_view, name='train_view'),
]
