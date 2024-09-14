import logging

from bunkrr_uploader import main

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        main()
        exit(0)
    except KeyboardInterrupt:
        print()
        logger.warning("Script stopped by user")
        exit(0)
    except Exception:
        logger.exception("Fatal error. Exiting...")
        exit(1)
