#!/bin/bash

# Safe rclone mount script for Google Drive Notes
LOCAL_DIR="$HOME/Sync/GoogleDrive/Notes"
BACKUP_DIR="$HOME/Sync/GoogleDrive/Notes_local_backup"
REMOTE="gdrive:Notes"

# Include dotfiles (e.g. .attachments/) in the globs below, and let an
# empty-directory glob expand to nothing instead of a literal "*".
shopt -s dotglob nullglob

echo "=== Google Drive Mount Script ==="

# 1. Ensure directories exist
mkdir -p "$LOCAL_DIR"
mkdir -p "$BACKUP_DIR"

# 2. Backup local notes to avoid being hidden by the mount.
#    Abort here rather than proceed to clear $LOCAL_DIR if the backup fails,
#    so a permissions/disk-space error can't turn into data loss.
echo "--> Backing up local notes to $BACKUP_DIR..."
local_entries=("$LOCAL_DIR"/*)
if [ "${#local_entries[@]}" -eq 0 ]; then
    echo "No local notes found to backup."
elif ! cp -R "$LOCAL_DIR"/* "$BACKUP_DIR/"; then
    echo "Error: Failed to back up local notes to $BACKUP_DIR. Aborting without touching $LOCAL_DIR." >&2
    exit 1
fi

# 3. Clean local directory (so mount doesn't complain about non-empty directory)
echo "--> Ensuring any old mount is unmounted..."
fusermount3 -u "$LOCAL_DIR" 2>/dev/null || true
echo "--> Clearing local directory before mounting..."
rm -rf "$LOCAL_DIR"/*

# 4. Perform the mount
echo "--> Mounting $REMOTE to $LOCAL_DIR in daemon background mode..."
rclone mount "$REMOTE" "$LOCAL_DIR" --vfs-cache-mode writes --daemon

if [ $? -eq 0 ]; then
    echo "--> Mount successful. Waiting 2 seconds for filesystem to initialize..."
    sleep 2

    # 5. Restore local backup files into the mount (which uploads them to Google Drive)
    echo "--> Merging local notes back into the mounted Google Drive folder..."
    backup_entries=("$BACKUP_DIR"/*)
    if [ "${#backup_entries[@]}" -gt 0 ]; then
        cp -R "$BACKUP_DIR"/* "$LOCAL_DIR/"
        echo "--> Local notes restored and syncing."
    fi

    # 6. Verify contents
    echo "--> Current directory contents:"
    ls -la "$LOCAL_DIR"

    echo ""
    echo "Success! Your local notes and remote Google Drive notes are now merged in $LOCAL_DIR."
    echo "Any edits in the app will now sync automatically to Google Drive."
else
    echo "Error: Failed to mount Google Drive remote."
fi
