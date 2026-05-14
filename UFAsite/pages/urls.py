from .views import (
    home_page_view, webhook,
    admin_login, admin_logout, admin_dashboard,
    admin_users, admin_user_toggle, admin_user_delete,
    admin_stations, admin_station_edit,
    admin_commands, admin_run_command,
)
from django.urls import path

urlpatterns = [
    path('', home_page_view, name='home'),
    path('webhook/', webhook, name='webhook'),

    # Admin Panel
    path('admin-panel/login/', admin_login, name='admin_login'),
    path('admin-panel/logout/', admin_logout, name='admin_logout'),
    path('admin-panel/', admin_dashboard, name='admin_dashboard'),
    path('admin-panel/users/', admin_users, name='admin_users'),
    path('admin-panel/users/<int:user_id>/toggle/', admin_user_toggle, name='admin_user_toggle'),
    path('admin-panel/users/<int:user_id>/delete/', admin_user_delete, name='admin_user_delete'),
    path('admin-panel/stations/', admin_stations, name='admin_stations'),
    path('admin-panel/stations/<str:station_id>/edit/', admin_station_edit, name='admin_station_edit'),
    path('admin-panel/commands/', admin_commands, name='admin_commands'),
    path('admin-panel/run-command/', admin_run_command, name='admin_run_command'),
]