from django.db import models

class WaterStations(models.Model):
    station_id = models.CharField(primary_key=True, max_length=255)
    station_code = models.CharField(max_length=255, blank=True, null=True)
    station_name = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    warning_level = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    critical_level = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_active = models.IntegerField(default=1)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'water_stations'

    def __str__(self):
        return f"{self.station_name} ({self.station_id})"

class WaterLevels(models.Model):
    water_level_id = models.AutoField(primary_key=True)
    station = models.ForeignKey(WaterStations, models.DO_NOTHING, db_column='station_id')
    water_level = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    rainfall = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    risk_level = models.IntegerField(default=0, null=True, blank=True)
    recorded_at = models.DateTimeField(blank=True, null=True)
    data_source = models.CharField(max_length=255, blank=True, null=True)
    is_processed = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = 'water_levels'

    def __str__(self):
        return f"{self.station.station_name} - {self.water_level}m"

class Users(models.Model):
    user_id = models.AutoField(primary_key=True)
    line_user_id = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255, blank=True, null=True)
    picture_url = models.CharField(max_length=1024, blank=True, null=True)
    status_message = models.CharField(max_length=1024, blank=True, null=True)
    is_active = models.IntegerField(default=1) # 1=active, 0=inactive
    last_subscribed_at = models.DateTimeField(blank=True, null=True)
    registered_at = models.DateTimeField(null=True, blank=True)
    is_admin = models.IntegerField(default=0)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.display_name or 'User'} ({self.line_user_id})"