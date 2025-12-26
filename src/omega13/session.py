"""
Session management for TimeMachine.

Handles session lifecycle including:
- Creating unique session directories in temp storage
- Managing recording metadata
- Saving sessions to permanent storage
- Cleanup and disposal of temporary files
"""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SessionRecording:
    """Represents a single recording within a session."""

    def __init__(
        self,
        filename: str,
        timestamp: datetime,
        duration_seconds: float = 0.0,
        channels: int = 2,
        samplerate: int = 16000
    ):
        self.filename = filename
        self.timestamp = timestamp
        self.duration_seconds = duration_seconds
        self.channels = channels
        self.samplerate = samplerate

    def to_dict(self) -> Dict[str, Any]:
        """Serialize recording metadata to dictionary."""
        return {
            "filename": self.filename,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
            "channels": self.channels,
            "samplerate": self.samplerate
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionRecording':
        """Deserialize recording metadata from dictionary."""
        return cls(
            filename=data["filename"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            duration_seconds=data.get("duration_seconds", 0.0),
            channels=data.get("channels", 2),
            samplerate=data.get("samplerate", 16000)
        )


class Session:
    """Represents a recording session with metadata and file management."""

    def __init__(
        self,
        session_id: str,
        session_dir: Path,
        created_at: Optional[datetime] = None
    ):
        self.session_id = session_id
        self.session_dir = session_dir
        self.created_at = created_at or datetime.now()
        self.recordings: List[SessionRecording] = []
        self.transcriptions: List[str] = []
        self.saved = False
        self.save_location: Optional[Path] = None

        # Ensure directory structure exists
        self.recordings_dir = self.session_dir / "recordings"
        self.transcriptions_dir = self.session_dir / "transcriptions"
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.transcriptions_dir.mkdir(parents=True, exist_ok=True)

    def get_next_recording_number(self) -> int:
        """Get the next sequential recording number."""
        return len(self.recordings) + 1

    def get_next_recording_path(self) -> Path:
        """Generate path for next recording with sequential numbering."""
        num = self.get_next_recording_number()
        filename = f"{num:03d}.wav"
        return self.recordings_dir / filename

    def register_recording(
        self,
        filepath: Path,
        duration_seconds: float = 0.0,
        channels: int = 2,
        samplerate: int = 16000
    ) -> None:
        """Register a completed recording in the session."""
        recording = SessionRecording(
            filename=filepath.name,
            timestamp=datetime.now(),
            duration_seconds=duration_seconds,
            channels=channels,
            samplerate=samplerate
        )
        self.recordings.append(recording)
        self.save_metadata()
        self._sync_to_save_location()

    def add_transcription(self, text: str) -> None:
        """
        Add a transcription to the session with overlap deduplication.
        
        Compares the new text with the previous transcriptions to find the
        longest word-based suffix-prefix overlap and strips it.
        """
        if not text:
            return

        # Canonicalize text (strip whitespace)
        new_text = text.strip()
        if not new_text:
            return

        # If no history, just add it
        if not self.transcriptions:
            self.transcriptions.append(new_text)
            self.save_metadata()
            self._sync_to_save_location()
            return

        # Join the last few transcriptions to check for overlap
        # Using the last 5 transcriptions or ~500 words should be enough context
        history_context = " ".join(self.transcriptions[-5:]).split()
        new_words = new_text.split()

        # Find the longest suffix of history that matches the prefix of new_words
        max_overlap = 0
        max_search = min(len(history_context), len(new_words))
        
        for i in range(1, max_search + 1):
            if history_context[-i:] == new_words[:i]:
                max_overlap = i

        # Extract only the unique part
        unique_segment = " ".join(new_words[max_overlap:])
        
        if unique_segment:
            self.transcriptions.append(unique_segment)
            self.save_metadata()
            self._sync_to_save_location()

    def get_metadata_path(self) -> Path:
        """Get path to session metadata file."""
        return self.session_dir / "session.json"

    def _sync_to_save_location(self) -> None:
        """Sync new recordings and metadata to permanent save location if session is 'saved'."""
        if not self.saved or not self.save_location:
            return

        logger.debug(f"Syncing session {self.session_id} to {self.save_location}")
        try:
            # Sync metadata
            shutil.copy2(self.get_metadata_path(), self.save_location / "session.json")

            # Sync recordings
            src_recordings = self.session_dir / "recordings"
            dst_recordings = self.save_location / "recordings"
            dst_recordings.mkdir(parents=True, exist_ok=True)
            for f in src_recordings.iterdir():
                if f.is_file():
                    target = dst_recordings / f.name
                    if not target.exists():
                        shutil.copy2(f, target)

            # Sync transcriptions (the .txt files per recording)
            src_trans = self.session_dir / "transcriptions"
            dst_trans = self.save_location / "transcriptions"
            dst_trans.mkdir(parents=True, exist_ok=True)
            for f in src_trans.iterdir():
                if f.is_file():
                    target = dst_trans / f.name
                    if not target.exists():
                        shutil.copy2(f, target)
        except Exception as e:
            logger.error(f"Failed to sync session to save location: {e}")

    def save_metadata(self) -> None:
        """Save session metadata to JSON file."""
        metadata = {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "recordings": [r.to_dict() for r in self.recordings],
            "transcriptions": self.transcriptions,
            "saved": self.saved,
            "save_location": str(self.save_location) if self.save_location else None
        }

        try:
            with open(self.get_metadata_path(), 'w') as f:
                json.dump(metadata, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save session metadata: {e}")

    @classmethod
    def load_from_directory(cls, session_dir: Path) -> 'Session':
        """Load existing session from directory."""
        metadata_path = session_dir / "session.json"

        if not metadata_path.exists():
            raise FileNotFoundError(f"Session metadata not found: {metadata_path}")

        with open(metadata_path, 'r') as f:
            data = json.load(f)

        session = cls(
            session_id=data["session_id"],
            session_dir=session_dir,
            created_at=datetime.fromisoformat(data["created_at"])
        )

        session.recordings = [
            SessionRecording.from_dict(r) for r in data.get("recordings", [])
        ]
        session.transcriptions = data.get("transcriptions", [])
        session.saved = data.get("saved", False)

        save_loc = data.get("save_location")
        session.save_location = Path(save_loc) if save_loc else None

        return session

    def get_info(self) -> Dict[str, Any]:
        """Get session information for UI display."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "recording_count": len(self.recordings),
            "saved": self.saved,
            "save_location": self.save_location,
            "total_duration": sum(r.duration_seconds for r in self.recordings)
        }


class SessionManager:
    """Manages session lifecycle and operations."""

    def __init__(self, temp_root: Optional[Path] = None):
        """
        Initialize session manager.

        Args:
            temp_root: Root directory for temporary sessions.
                      Defaults to /tmp/omega13
        """
        self.temp_root = temp_root or Path("/tmp/omega13")
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.current_session: Optional[Session] = None

    def create_session(self) -> Session:
        """
        Create a new session with unique ID and directory structure.

        Returns:
            New Session object
        """
        # Generate unique session ID with timestamp for sorting
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        uuid_str = str(uuid.uuid4())[:8]
        session_id = f"session_{timestamp_str}_{uuid_str}"

        # Create session directory
        session_dir = self.temp_root / session_id

        # Create session object (will create directory structure)
        self.current_session = Session(session_id, session_dir)
        self.current_session.save_metadata()

        logger.info(f"Created new session: {session_id}")
        return self.current_session

    def get_current_session(self) -> Optional[Session]:
        """Get the current active session."""
        return self.current_session

    def save_session(self, destination: Path, title: Optional[str] = None) -> bool:
        """
        Save session to permanent storage.

        Copies all recordings and metadata to destination directory.
        Creates a subdirectory named with the session ID.

        Args:
            destination: Parent directory where session will be saved
            title: Optional title to include in the session directory name

        Returns:
            True if save successful, False otherwise
        """
        if not self.current_session:
            logger.error("No active session to save")
            return False

        if not destination.exists() or not destination.is_dir():
            logger.error(f"Invalid destination directory: {destination}")
            return False

        try:
            # Create timestamped directory name for better organization
            timestamp = self.current_session.created_at.strftime("%Y-%m-%d_%H-%M-%S")
            session_name = f"omega13_session_{timestamp}"
            
            if title:
                # Sanitize title (replace non-alphanumeric with underscores)
                import re
                sanitized_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
                session_name = f"{session_name}_{sanitized_title}"
            
            final_destination = destination / session_name

            # Copy entire session directory
            shutil.copytree(
                self.current_session.session_dir,
                final_destination,
                dirs_exist_ok=True
            )

            # Update session metadata
            self.current_session.saved = True
            self.current_session.save_location = final_destination
            self.current_session.save_metadata()

            # Also update metadata in the saved location
            saved_session = Session.load_from_directory(final_destination)
            saved_session.saved = True
            saved_session.save_location = final_destination
            saved_session.save_metadata()

            logger.info(f"Session saved to: {final_destination}")
            return True

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False

    def discard_session(self) -> bool:
        """
        Discard current session and cleanup temporary files.

        Returns:
            True if cleanup successful, False otherwise
        """
        if not self.current_session:
            return True

        try:
            session_dir = self.current_session.session_dir

            # Only delete if not already saved
            if session_dir.exists() and not self.current_session.saved:
                shutil.rmtree(session_dir)
                logger.info(f"Discarded session: {self.current_session.session_id}")

            self.current_session = None
            return True

        except Exception as e:
            logger.error(f"Failed to discard session: {e}")
            return False

    def cleanup_old_sessions(self, days: int = 7) -> int:
        """
        Clean up temporary sessions older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of sessions cleaned up
        """
        if not self.temp_root.exists():
            return 0

        cleaned = 0
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)

        try:
            for session_dir in self.temp_root.iterdir():
                if not session_dir.is_dir():
                    continue

                # Check if session is old enough
                mtime = session_dir.stat().st_mtime
                if mtime < cutoff_time:
                    # Skip current session
                    if self.current_session and session_dir == self.current_session.session_dir:
                        continue

                    try:
                        shutil.rmtree(session_dir)
                        cleaned += 1
                        logger.info(f"Cleaned up old session: {session_dir.name}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup {session_dir.name}: {e}")

            return cleaned

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return cleaned

    def list_temp_sessions(self) -> List[Dict[str, Any]]:
        """
        List all temporary sessions.

        Returns:
            List of session info dictionaries
        """
        sessions = []

        if not self.temp_root.exists():
            return sessions

        for session_dir in self.temp_root.iterdir():
            if not session_dir.is_dir():
                continue

            try:
                session = Session.load_from_directory(session_dir)
                sessions.append(session.get_info())
            except Exception as e:
                logger.warning(f"Failed to load session {session_dir.name}: {e}")

        return sessions

    def is_saved(self) -> bool:
        """Check if current session has been saved."""
        if not self.current_session:
            return True  # No session means nothing to save
        return self.current_session.saved

    def has_recordings(self) -> bool:
        """Check if current session has any recordings."""
        if not self.current_session:
            return False
        return len(self.current_session.recordings) > 0
