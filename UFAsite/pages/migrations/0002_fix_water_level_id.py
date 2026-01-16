from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0001_initial'),
    ]

    operations = [
        # Explicitly modify the water_level_id column to include AUTO_INCREMENT
        # This fixes the "Field 'water_level_id' doesn't have a default value" error in TiDB
        migrations.RunSQL(
            "ALTER TABLE water_levels MODIFY COLUMN water_level_id INT NOT NULL AUTO_INCREMENT;",
            reverse_sql="ALTER TABLE water_levels MODIFY COLUMN water_level_id INT NOT NULL;"
        ),
    ]
