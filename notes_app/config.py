import os

# Target directory for the notes
NOTES_DIR = os.path.expanduser("~/Sync/GoogleDrive/Notes/")

# rclone sync command — adjust remote name/path to match your rclone config
# Run `rclone listremotes` to see available remotes
RCLONE_SYNC_CMD = ['rclone', 'sync', NOTES_DIR.rstrip('/'), 'gdrive:Notes', '--quiet']

def ensure_notes_dir():
    """Ensure that the notes directory exists."""
    os.makedirs(NOTES_DIR, exist_ok=True)
    return NOTES_DIR
