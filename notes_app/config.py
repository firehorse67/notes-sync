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

import json

CONFIG_DIR = os.path.expanduser("~/.config/notes-sync")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

def load_local_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_local_config(config_dict):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            os.chmod(CONFIG_DIR, 0o700)
        except OSError:
            pass
            
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=4)
            
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except OSError:
            pass
    except Exception as e:
        print(f"Error saving config: {e}")
