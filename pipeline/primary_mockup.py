import time
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.gelato_client as gelato_client


class GelatoMockupTimeoutError(Exception):
    pass


def build_mockup_title(candidate: dict) -> str:
    return f"{candidate['niche']} - primary mockup"
