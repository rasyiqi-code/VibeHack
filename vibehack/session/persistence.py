import json
import uuid
from datetime import datetime
from vibehack.toolkit.manager import VIBEHACK_HOME

SESSIONS_DIR = VIBEHACK_HOME / "sessions"

def generate_session_id() -> str:
    """Creates a unique, timestamped session identifier."""
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

def save_session(session_id: str, state: dict):
    """Saves the current session state to disk."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSIONS_DIR / f"{session_id}.json"
    
    # Credential masking (simple regex or keyword based)
    # For now, we assume the history is saved as is in Alpha
    with open(session_file, "w") as f:
        json.dump(state, f, indent=4)
        
    return session_file

def load_session(session_id: str) -> dict:
    """Loads a previously saved session."""
    session_file = SESSIONS_DIR / f"{session_id}.json"
    if not session_file.exists():
        return None
        
    with open(session_file, "r") as f:
        return json.load(f)

def list_sessions():
    """Returns a list of all saved session IDs."""
    if not SESSIONS_DIR.exists():
        return []
        
    return [f.stem for f in SESSIONS_DIR.glob("*.json")]
