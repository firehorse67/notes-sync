import os

# Target directory for the notes
NOTES_DIR = os.path.expanduser("~/Sync/GoogleDrive/Notes/")

def ensure_notes_dir():
    """Ensure that the notes directory exists."""
    os.makedirs(NOTES_DIR, exist_ok=True)
    return NOTES_DIR
