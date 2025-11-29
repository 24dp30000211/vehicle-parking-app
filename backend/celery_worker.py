# celery_worker.py
from celery.schedules import crontab
from app import app  # Import your Flask app
from celery import Celery

def make_celery(app):
    """
    This function configures Celery to work with Flask.
    It reads the broker URL from the Flask config.
    """
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL'],
        include=['tasks']  # <-- IMPORTANT: Tells Celery to look for 'tasks.py'
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

# Configure Flask app for Celery
app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379/0',  # Connects to Redis
    CELERY_RESULT_BACKEND='redis://localhost:6379/0' # Stores results in Redis
)
# ... (after app.config.update(...))

# --- NEW: Configure Celery Beat (Scheduler) ---
app.config['CELERYBEAT_SCHEDULE'] = {
    'send-daily-reminder-every-minute': {
        'task': 'tasks.send_daily_reminders',
        # This runs every minute for testing
        'schedule': crontab(minute='*'),
        # To run at 7 PM daily, use this instead:
        # 'schedule': crontab(hour=19, minute=0),
    },
}

# Initialize Celery
celery = make_celery(app)