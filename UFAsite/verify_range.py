from pages.models import WaterLevels

# Check range for June
start = '2025-06-01'
end = '2025-07-01'
c = WaterLevels.objects.filter(station__station_id='TS16', recorded_at__gte=start, recorded_at__lt=end).count()
print(f"June Range Count: {c}")

# Check total for 2025 using year filter
c_year = WaterLevels.objects.filter(station__station_id='TS16', recorded_at__year=2025).count()
print(f"Year Filter Count: {c_year}")

# Print first few valid dates in June if any
qs = WaterLevels.objects.filter(station__station_id='TS16', recorded_at__gte=start, recorded_at__lt=end)
if qs.exists():
    print(f"Sample June record: {qs.first().recorded_at}")
else:
    print("No records found for June range.")
