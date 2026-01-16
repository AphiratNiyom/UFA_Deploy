#!/usr/bin/env bash
# exit on error
set -o errexit

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
elif [ -f "../requirements.txt" ]; then
    pip install -r ../requirements.txt
else
    echo "requirements.txt not found"
    exit 1
fi
python manage.py collectstatic --no-input
python manage.py migrate

# Create Superuser automatically (since Shell is unreliable on Free Tier)
python manage.py ensure_superuser