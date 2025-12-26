from django.urls import path
from .views import home_page_view, webhook

urlpatterns = [
    path('', home_page_view, name='home'),
    path('webhook/', webhook, name='webhook'), 
]