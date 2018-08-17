import pathlib
import logging
from datetime import datetime
from ._connection import Connection


def configure_logging(level=logging.INFO, show_in_console=True, dump_to_file=False):
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    fmt = logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")
    if show_in_console:
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    if dump_to_file:
        logs_store_path = pathlib.Path(".") / "logs"
        logs_store_path.mkdir(exist_ok=True)
        fh = logging.FileHandler(
             logs_store_path / f"{__name__}{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
