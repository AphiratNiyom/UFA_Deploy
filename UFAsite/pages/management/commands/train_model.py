from django.core.management.base import BaseCommand
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
from pages.models import WaterLevels

class Command(BaseCommand):
    help = 'Train and save a new prediction model for water risk level'

    def handle(self, *args, **options):
        self.stdout.write("Starting model training...")

        # Load data from the database
        water_levels = WaterLevels.objects.all()
        if not water_levels.exists():
            self.stdout.write(self.style.ERROR("No water level data found in the database."))
            return

        data = list(water_levels.values('water_level', 'risk_level', 'station_id'))
        df = pd.DataFrame(data)

        # Preprocessing
        df.dropna(inplace=True)

        # Define features (X) and target (y)
        features = ['water_level']
        target = 'risk_level'

        X = df[features]
        y = df[target]
        
        if len(df) < 2:
            self.stdout.write(self.style.ERROR("Not enough data to train the model. Need at least 2 samples."))
            return

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Train model
        # Using RandomForestClassifier as risk_level is categorical
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        # Evaluate model
        accuracy = model.score(X_test, y_test)
        self.stdout.write(self.style.SUCCESS(f"Model trained with accuracy: {accuracy}"))

        # Save model
        model_path = os.path.join(os.path.dirname(__file__), '..', '..', 'predictor_model.joblib')
        joblib.dump(model, model_path)
        self.stdout.write(self.style.SUCCESS(f"Model saved to {model_path}"))
