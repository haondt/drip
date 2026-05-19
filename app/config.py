import os
import re
import uuid
from . import datetime_util as dt

def parse_bool_env_var(var_name, default=False):
    value = os.getenv(var_name)
    if value is not None:
        value_str = str(value).lower()
        return value_str in ('true', '1') or \
               (value_str.isdigit() and int(value_str) != 0)
    return default



class Config:
    def __init__(self):
        self.is_development = os.getenv('DRIP_ENVIRONMENT', 'prod') in ['dev', 'development']
        self.log_template = os.getenv('DRIP_LOG_TEMPLATE', '%(name)s: %(message)s' if self.is_development else '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s')
        self.log_level = os.getenv('DRIP_LOG_LEVEL', 'INFO')
        self.server_port = int(os.getenv('DRIP_SERVER_PORT', 5001))
        self.db_path = os.getenv('DRIP_DB_PATH', '/data/drip.db')
        self.db_path = os.path.abspath(self.db_path)
        self.max_drops = int(os.getenv('DRIP_MAX_DROPS', 10))
        self.namespace_uuid = uuid.UUID(os.getenv('DRIP_NAMESPACE_UUID', '60a76c80-d399-11d9-b93c-0003939e0af6'))
        self.base_url = os.getenv('DRIP_BASE_URL')
        self.default_user_agent = os.getenv('DRIP_DEFAULT_USER_AGENT', 'drip/0.1 (+https://github.com/haondt/drip)')

        self.feed_read_timeout = dt.parse_timespan(os.getenv('DRIP_FEED_READ_TIMEOUT', '30s'))
        self.feed_read_max_interval = dt.parse_timespan(os.getenv('DRIP_FEED_READ_MAX_INTERVAL', '24h'))
        self.feed_read_default_interval = dt.parse_timespan(os.getenv('DRIP_FEED_READ_DEFAULT_INTERVAL', '15m'))
        self.feed_read_min_interval = dt.parse_timespan(os.getenv('DRIP_FEED_READ_MIN_INTERVAL', '5m'))
        # multiplier for when feed is slower than expected
        self.feed_read_backoff_factor = float(os.getenv('DRIP_FEED_READ_BACKOFF_FACTOR', 2.0))
        # multiplier for when feed is faster than expected
        self.feed_read_accel_factor = float(os.getenv('DRIP_FEED_READ_ACCEL_FACTOR', 0.5))
        self.feed_read_jitter_factor = float(os.getenv('DRIP_FEED_READ_JITTER_FACTOR', 0.2))
        self.feed_read_tick_rate = dt.parse_timespan(os.getenv('DRIP_FEED_READ_TICK_RATE', '30s'))
        self.feed_read_empty_backoff_threshold = int(os.getenv('DRIP_FEED_EMPTY_BACKOFF_THRESHOLD', 3))

config = Config()

