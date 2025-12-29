"""
Omega-13: Retroactive Audio Recorder
A tribute to Galaxy Quest's time-rewind device
"""

from .app import Omega13App
from .transcription import TranscriptionService

# It is often helpful to expose 'main' here too,
# in case someone wants to run it via code: omega13.main()
from .app import main

__version__ = "2.3.0"

__all__ = ["Omega13App", "TranscriptionService", "main"]