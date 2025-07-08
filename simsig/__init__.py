

"""
simsig: Some description, maybe?
"""

import importlib.metadata

_metadata = importlib.metadata.metadata("simsig")
__version__ = _metadata["Version"]
__author__ = _metadata["Author-email"]
__license__ = _metadata["License"]

__all__ = [
]
