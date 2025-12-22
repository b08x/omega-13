from pathlib import Path
from timemachine.session import Session
import shutil
import os

def test_deduplication():
    temp_dir = Path("./temp_test_session")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        session = Session("test_id", temp_dir)
        
        # Test 1: Simple append
        session.add_transcription("Hello world")
        print(f"Test 1: {session.transcriptions}")
        assert session.transcriptions == ["Hello world"]
        
        # Test 2: Overlapping append
        # This simulates the user's case where the second transcription contains the first
        session.add_transcription("Hello world and then some")
        print(f"Test 2: {session.transcriptions}")
        # Expected: ["Hello world", "and then some"]
        assert session.transcriptions == ["Hello world", "and then some"]
        
        # Test 3: Partial overlap (word based)
        session.add_transcription("then some more text here")
        print(f"Test 3: {session.transcriptions}")
        # Expected: ["Hello world", "and then some", "more text here"]
        assert session.transcriptions == ["Hello world", "and then some", "more text here"]

        # Test 4: No overlap
        session.add_transcription("Completely new sentence")
        print(f"Test 4: {session.transcriptions}")
        assert session.transcriptions == ["Hello world", "and then some", "more text here", "Completely new sentence"]
        
        print("All deduplication tests passed!")
        
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    # Ensure src is in python path
    import sys
    sys.path.append(os.path.abspath("./src"))
    test_deduplication()
