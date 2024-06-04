"""Entry point"""

import logging
import sched
import sys

from datetime import datetime

from vc_autoposter.config import Config, load_config
from vc_autoposter.poster import Poster

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.INFO)
fmter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(fmter)
logger.addHandler(handler)


def schedule_post(scheduler: sched.scheduler, delay: int, poster: Poster):
    """Schedule new post"""
    new_delay = delay
    config: Config = load_config()
    if int(delay / 60) != config.min_delay:
        new_delay = config.min_delay * 60
        logger.info(
            "Delay has been updated. It was %s minutes, and is now %s.",
            int(delay / 60),
            int(new_delay / 60),
        )

    scheduler.enter(
        new_delay,
        1,
        schedule_post,
        (
            scheduler,
            new_delay,
            poster,
        ),
    )
    poster.update_from_config(config)
    poster.post_new_vc()


def main():
    """main"""
    logger.info("VC Auto-poster starting...")
    config: Config = load_config()
    poster: Poster = Poster.from_config(config)
    logger.info("VC Auto-poster initialized!")
    logger.info(
        "VCs will be posted every %s minutes to topic ID #%s.",
        config.min_delay,
        config.topic,
    )
    scheduler = sched.scheduler()
    delay: int = config.min_delay * 60
    initial_delay: int = delay
    if config.auto_align and config.min_delay > 1 and 60 % config.min_delay == 0:
        logger.info(
            "Auto-align enabled, and %s divides 60. Changing initial delay.",
            config.min_delay,
        )
        current = datetime.now()
        initial_delay = config.min_delay - (current.minute % config.min_delay)
        logger.info(
            "Current minutes is %s. New initial delay is %s minutes.",
            current.minute,
            initial_delay,
        )
        initial_delay = initial_delay * 60

    scheduler.enter(initial_delay, 1, schedule_post, (scheduler, delay, poster))
    scheduler.run()


if __name__ == "__main__":
    sys.exit(main())
