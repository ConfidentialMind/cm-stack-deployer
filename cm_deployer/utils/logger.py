import logging
import sys

def setup_logger(debug: bool = False):
    """Configure logging for the application.
    
    Args:
        debug: Enable debug logging if True
    """
    level = logging.DEBUG if debug else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Quiet some noisy loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('git').setLevel(logging.WARNING)