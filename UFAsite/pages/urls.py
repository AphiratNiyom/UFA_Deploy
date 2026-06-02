from .views import WebViews, LineWebhook, AdminViews
from django.urls import path

urlpatterns = [
    path('', WebViews.home_page_view, name='home'),
    path('webhook/', LineWebhook.as_view(), name='webhook'),

    # Admin Panel
    path('admin-panel/login/', AdminViews.admin_login, name='admin_login'),
    path('admin-panel/logout/', AdminViews.admin_logout, name='admin_logout'),
    path('admin-panel/', AdminViews.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/users/', AdminViews.admin_users, name='admin_users'),
    path('admin-panel/users/<int:user_id>/toggle/', AdminViews.admin_user_toggle, name='admin_user_toggle'),
    path('admin-panel/users/<int:user_id>/delete/', AdminViews.admin_user_delete, name='admin_user_delete'),
    path('admin-panel/stations/', AdminViews.admin_stations, name='admin_stations'),
    path('admin-panel/stations/<str:station_id>/edit/', AdminViews.admin_station_edit, name='admin_station_edit'),
    path('admin-panel/commands/', AdminViews.admin_commands, name='admin_commands'),
    path('admin-panel/run-command/', AdminViews.admin_run_command, name='admin_run_command'),
]