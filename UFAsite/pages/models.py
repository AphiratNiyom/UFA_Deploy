from django.db import models

class WaterStations(models.Model):
    station_id = models.CharField(primary_key=True, max_length=255)
    station_name = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'water_stations'

class WaterLevels(models.Model):
    water_level_id = models.AutoField(primary_key=True)
    water_level = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    recorded_at = models.DateTimeField(blank=True, null=True)
    risk_level = models.IntegerField(default=0, null=True, blank=True)

    station = models.ForeignKey(WaterStations, models.DO_NOTHING, db_column='station_id')

    class Meta:
        managed = True
        db_table = 'water_levels'

class Users(models.Model):
    line_user_id = models.CharField(primary_key=True, max_length=255)
    is_active = models.IntegerField(default=1)
    is_admin = models.IntegerField(default=0)
    registered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'users'

def __str__(self):
        return f"{self.station.station_name} - {self.water_level}m"