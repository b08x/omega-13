from pathlib import Path
from omega13.session import Session, SessionManager
import shutil
import os
import json
import time

def test_incremental_save():
    temp_root = Path("./temp_test_root")
    save_dest = Path("./temp_save_dest")
    
    # Cleanup from previous runs
    if temp_root.exists(): shutil.rmtree(temp_root)
    if save_dest.exists(): shutil.rmtree(save_dest)
    
    temp_root.mkdir(exist_ok=True)
    save_dest.mkdir(exist_ok=True)
    
    try:
        manager = SessionManager(temp_root=temp_root)
        session = manager.create_session()
        
        # 1. Add first recording
        rec1_path = session.get_next_recording_path()
        rec1_path.touch() # Simulate recording file
        session.register_recording(rec1_path)
        
        # 2. First save
        print(f"Saving session for the first time...")
        assert manager.save_session(save_dest) == True
        
        save_loc = session.save_location
        assert save_loc is not None
        assert save_loc.exists()
        assert (save_loc / "recordings" / "001.wav").exists()
        
        with open(save_loc / "session.json", "r") as f:
            data = json.load(f)
            assert len(data["recordings"]) == 1
            assert data["saved"] == True
        
        # 3. Add second recording and transcription
        print(f"Adding more content to session...")
        rec2_path = session.get_next_recording_path()
        rec2_path.touch()
        session.register_recording(rec2_path)
        session.add_transcription("First transcription")
        
        # 4. Second save (incremental)
        print(f"Saving session incrementally...")
        # In app.py we do: manager.save_session(session.save_location.parent)
        assert manager.save_session(save_loc.parent) == True
        
        assert save_loc.exists()
        assert (save_loc / "recordings" / "001.wav").exists()
        assert (save_loc / "recordings" / "002.wav").exists()
        
        with open(save_loc / "session.json", "r") as f:
            data = json.load(f)
            assert len(data["recordings"]) == 2
            assert len(data["transcriptions"]) == 1
            assert data["transcriptions"][0] == "First transcription"
            assert data["saved"] == True
            
        print("Incremental save verification PASSED!")
        
    finally:
        if temp_root.exists(): shutil.rmtree(temp_root)
        if save_dest.exists(): shutil.rmtree(save_dest)

if __name__ == "__main__":
    # Ensure src is in python path
    import sys
    sys.path.append(os.path.abspath("./src"))
    test_incremental_save()
