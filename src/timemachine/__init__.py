"""
TimeMachine: Retroactive Audio Recorder
"""

from .app import TimeMachineApp
from .transcription import TranscriptionService

# It is often helpful to expose 'main' here too, 
# in case someone wants to run it via code: timemachine.main()
from .app import main

__version__ = "2.0.0"

__all__ = ["TimeMachineApp", "TranscriptionService", "main"]