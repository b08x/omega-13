"""Omega-13 UI Package.

This package contains all Textual UI components for the Omega-13 application.
All widgets and screens are self-contained and import Textual internally.
"""

from .widgets import (
    VUMeter,
    SilenceCountdown,
    TranscriptionDisplay,
)

from .screens import (
    InputSelectionScreen,
    TranscriptionSettingsScreen,
    SessionTitleScreen,
    DirectorySelectionScreen,
    NewSessionPromptScreen,
    SavePromptScreen,
)

__all__ = [
    # Widgets
    "VUMeter",
    "SilenceCountdown",
    "TranscriptionDisplay",
    # Modal Screens
    "InputSelectionScreen",
    "TranscriptionSettingsScreen",
    "SessionTitleScreen",
    "DirectorySelectionScreen",
    "NewSessionPromptScreen",
    "SavePromptScreen",
]