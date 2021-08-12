import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from config_utils import toBool  # noqa: E402


DB_FALLBACK = toBool(os.environ.get("SLICER_DOWNLOAD_DB_FALLBACK", False))
DEBUG = toBool(os.environ.get("SLICER_DOWNLOAD_DEBUG", False))
TEMPLATES_AUTO_RELOAD = toBool(os.environ.get("SLICER_DOWNLOAD_TEMPLATES_AUTO_RELOAD", True))
