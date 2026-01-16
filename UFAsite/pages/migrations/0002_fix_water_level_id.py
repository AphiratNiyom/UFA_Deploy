from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0001_initial'),
    ]

    operations = [
        # 1. Rename existing table to backup
        migrations.RunSQL(
            "RENAME TABLE water_levels TO water_levels_backup;",
            reverse_sql="RENAME TABLE water_levels_backup TO water_levels;"
        ),

        # 2. Create the new table with correct schema (AUTO_INCREMENT)
        migrations.CreateModel(
            name='WaterLevels',
            fields=[
                # AutoField -> INT AUTO_INCREMENT
                ('water_level_id', models.AutoField(primary_key=True, serialize=False)),
                ('water_level', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('rainfall', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('risk_level', models.IntegerField(blank=True, default=0, null=True)),
                ('recorded_at', models.DateTimeField(blank=True, null=True)),
                ('data_source', models.CharField(blank=True, max_length=255, null=True)),
                ('is_processed', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
                ('station', models.ForeignKey(db_column='station_id', on_delete=django.db.models.deletion.DO_NOTHING, to='pages.waterstations')),
            ],
            options={
                'db_table': 'water_levels',
            },
        ),

        # 3. Copy data from backup to new table
        # We explicitly map columns to ensure data integrity
        # water_level_id is preserved if it exists
        migrations.RunSQL(
            """
            INSERT INTO water_levels (
                water_level_id, station_id, water_level, rainfall, risk_level, 
                recorded_at, data_source, is_processed, created_at, updated_at
            )
            SELECT 
                water_level_id, station_id, water_level, rainfall, risk_level, 
                recorded_at, data_source, is_processed, created_at, updated_at
            FROM water_levels_backup;
            """,
            reverse_sql="TRUNCATE TABLE water_levels;"
        ),

        # 4. Drop the backup table
        migrations.RunSQL(
            "DROP TABLE water_levels_backup;",
            reverse_sql=""  # Cannot easily reverse a drop without backup
        ),
    ]
