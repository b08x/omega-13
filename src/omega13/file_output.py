"""
File output integration for omega-13.

Provides a safe mechanism for appending transcription results to a daily markdown file.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FileOutputResult:
    """Result container for file output operations."""
    success: bool
    message: str
    error: Optional[str] = None

class FileOutputHandler:
    def __init__(self):
        pass

    def append_to_daily_file(self, content: str, directory_path: str) -> FileOutputResult:
        """
        Append content to today's daily file in the specified directory.
        """
        if not content or not content.strip():
            return FileOutputResult(success=False, message="Cannot append empty content")
            
        if not directory_path:
            return FileOutputResult(success=False, message="Output directory is not configured")

        try:
            dir_path = Path(directory_path).expanduser().resolve()
            dir_path.mkdir(parents=True, exist_ok=True)
            
            today = datetime.now().strftime("%Y-%m-%d")
            file_path = dir_path / f"{today}.md"
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_content = f"\n[{timestamp}] {content.strip()}\n"
            
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(formatted_content)
                
            logger.info(f"Successfully appended to {file_path.name}")
            return FileOutputResult(success=True, message=f"Appended to {file_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to write to file: {e}")
            return FileOutputResult(success=False, message="Failed to write to file", error=str(e))

file_output = FileOutputHandler()
