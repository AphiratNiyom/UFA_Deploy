from django.contrib import admin
from .models import WaterStations, WaterLevels, Users

@admin.register(WaterStations)
class WaterStationsAdmin(admin.ModelAdmin):
    list_display = ('station_id', 'station_name', 'warning_level', 'critical_level', 'is_active', 'updated_at')
    search_fields = ('station_name', 'station_id')

@admin.register(WaterLevels)
class WaterLevelsAdmin(admin.ModelAdmin):
    list_display = ('station', 'water_level', 'risk_level', 'recorded_at', 'created_at')
    list_filter = ('station', 'risk_level', 'recorded_at')
    ordering = ('-recorded_at',)

@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'line_user_id', 'is_active', 'last_subscribed_at')
    search_fields = ('display_name', 'line_user_id')
