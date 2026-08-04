from core.services.logger import log_manager

log_manager.setup()

log = log_manager.instance

log.info("Information message")
log.success("Everything is working")
log.warning("Warning example")
log.error("Error example")
log.debug("Debug example")