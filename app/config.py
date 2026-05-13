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
        self.feed_polling_period = dt.parse_timespan(os.getenv('DRIP_FEED_POLLING_PERIOD', '30m'))
        self.max_drops = int(os.getenv('DRIP_MAX_DROPS', 10))
        self.namespace_uuid = uuid.UUID(os.getenv('DRIP_NAMESPACE_UUID', '60a76c80-d399-11d9-b93c-0003939e0af6'))
        self.feed_read_timeout = dt.parse_timespan(os.getenv('DRIP_FEED_READ_TIMEOUT', '30s'))
        self.base_url = os.getenv('DRIP_BASE_URL')

config = Config()

