import worker
import logging
import threading
from config import CRON_INTERVAL


def cron_job():
    logging.info("Cron Started.")
    worker.queue_all_user()
    threading.Timer(CRON_INTERVAL, cron_job).start()


if __name__ == '__main__':
    cron_job()
