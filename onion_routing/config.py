import os
from dotenv import load_dotenv

# Load global variables from .env file into the environment
load_dotenv()

RELAY_TTL_SECONDS = int(os.getenv("RELAY_TTL_SECONDS", 45))
HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", 10))
DEFAULT_CELL_SIZE = int(os.getenv("DEFAULT_CELL_SIZE", 16384))
MIN_PATH_HOPS = int(os.getenv("MIN_PATH_HOPS", 3))

# Timing obfuscation jitter bounds
JITTER_MIN = float(os.getenv("JITTER_MIN", 0.01))
JITTER_MAX = float(os.getenv("JITTER_MAX", 0.1))
