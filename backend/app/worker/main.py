from arq.cron import cron
from app.core.config import settings
from app.worker.tasks.outbox import process_outbox_events


class WorkerSettings:
    redis_settings = settings.redis_url
    functions = [process_outbox_events]
    cron_jobs = [
        # Запуск обработки outbox каждую минуту
        cron(process_outbox_events, minute=set(range(60)))
    ]
