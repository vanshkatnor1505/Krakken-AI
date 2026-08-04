from app.config import config
from core.services.container import container
from core.services.logger import log_manager

print("Starting test...")

log_manager.setup()

print("Logger initialized")

logger = log_manager.instance

container.register_singleton("config", config)
container.register_singleton("logger", logger)

print("Services registered")

cfg = container.get("config")
log = container.get("logger")

print("Services retrieved")

log.success("Container initialized successfully.")
log.info(cfg.app_name)
log.info(cfg.app_version)

print("Finished")