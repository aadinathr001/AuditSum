from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from dotenv import load_dotenv
load_dotenv()

limiter = Limiter(key_func=get_remote_address)
RUN_RATE_LIMIT = f"{os.environ.get('RATE_LIMIT_PER_MINUTE', '5')}/minute"