"""
Omega-13: Retroactive Audio Recorder
A tribute to Galaxy Quest's time-rewind device
"""

# Lazy imports to avoid pulling in heavy dependencies (JACK) at package import time
def __getattr__(name: str):
    if name == "Omega13App":
        from .app import Omega13App
        return Omega13App
    if name == "TranscriptionService":
        from .transcription import TranscriptionService
        return TranscriptionService
    if name == "main":
        from .app import main
        return main
    raise AttributeError(f"module 'omega13' has no attribute '{name}'")


__version__ = "2.3.0"

__all__ = ["Omega13App", "TranscriptionService", "main"]