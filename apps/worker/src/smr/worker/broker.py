"""The broker and the scheduler: `taskiq worker smr.worker.broker:broker`.

Built when imported, from the environment: the processes that import it are the
worker and the scheduler containers.
"""

from __future__ import annotations

import logging

from dishka.integrations.taskiq import setup_dishka
from taskiq import TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisStreamBroker

from smr.core.config import RedisSettings

from .di import make_container
from .tasks import back_up, deliver_outbox, purge_expired, queue_reminders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# Required, read from the environment.
_redis = RedisSettings()  # pyright: ignore[reportCallIssue]
_MOSCOW = "Europe/Moscow"

broker = RedisStreamBroker(url=_redis.url(_redis.tasks_db), queue_name="seminarist")
container = make_container()
setup_dishka(container, broker)

_ = broker.register_task(
    deliver_outbox,
    task_name="deliver_outbox",
    schedule=[{"interval": 10}],
)
_ = broker.register_task(
    queue_reminders,
    task_name="queue_reminders",
    schedule=[{"cron": "*/5 * * * *"}],
)
_ = broker.register_task(
    back_up,
    task_name="back_up",
    schedule=[{"cron": "0 3 * * *", "cron_offset": _MOSCOW}],
)
_ = broker.register_task(
    purge_expired,
    task_name="purge_expired",
    schedule=[{"cron": "0 4 * * *", "cron_offset": _MOSCOW}],
)

scheduler = TaskiqScheduler(broker=broker, sources=[LabelScheduleSource(broker)])


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _close_container(_state: TaskiqState) -> None:
    """Close the container, and with it the engine and the bot's session."""
    await container.close()
