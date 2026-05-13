from fastapi import FastAPI
from . import routes, scheduler
from .config import  config
import logging, datetime, asyncio, signal
from contextlib import asynccontextmanager

logging.Formatter.formatTime = (lambda self, record, datefmt=None: datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc).astimezone().isoformat(sep="T",timespec="milliseconds"))

_logger = logging.getLogger(__name__)

def _handle_scheduler_exception(task: asyncio.Task):
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        _logger.critical(f"Scheduler crashed: {exc}", exc_info=exc)
        import os
        os.kill(os.getpid(), signal.SIGTERM)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(scheduler.scheduler_loop())
    task.add_done_callback(_handle_scheduler_exception)
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

def create_app():
    app = FastAPI(title="FastAPI + HTMX + Bulma + WebSockets", version="1.0.0", lifespan=lifespan)
    logging.basicConfig(format=config.log_template, level=logging.getLevelName(config.log_level))
    routes.add_routes(app)
    return app

