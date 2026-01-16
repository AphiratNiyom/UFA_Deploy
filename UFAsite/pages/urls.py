from .views import home_page_view, webhook
from django.urls import path

urlpatterns = [
    path('', home_page_view, name='home'),
    path('webhook/', webhook, name='webhook'),
]