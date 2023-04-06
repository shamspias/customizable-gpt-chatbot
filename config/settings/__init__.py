"""For production, we'll automatically generate settings from prod.py via ci/cd script"""
import os
from dotenv import load_dotenv

load_dotenv()
# DEV = False
env_name = os.getenv('ENV_NAME', 'local')
from key_values import *

if env_name == "prod":
    from .prod import *
elif env_name == "stage":
    from .stage import *
else:
    from .local import *
