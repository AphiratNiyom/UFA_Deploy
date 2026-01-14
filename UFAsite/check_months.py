print("Month Distribution for TS2 (2025):")
for m in range(1, 13):
    c = WaterLevels.objects.filter(station__station_id='TS2', recorded_at__year=2025, recorded_at__month=m).count()
    print(f"Month {m}: {c}")
