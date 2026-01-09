from django.core.management.base import BaseCommand
from pages.predictor import train_and_save_model

class Command(BaseCommand):
    help = 'Fetches all historical data, trains a new prediction model, and saves it.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting model training...'))
        
        try:
            model_path = train_and_save_model()
            if model_path:
                self.stdout.write(self.style.SUCCESS(f'Successfully trained and saved model to {model_path}'))
            else:
                self.stdout.write(self.style.WARNING('Model training did not complete. See console for details.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'An error occurred during model training: {e}'))
