#!/bin/bash

# Safe rclone mount script for Google Drive Notes
LOCAL_DIR="$HOME/Sync/GoogleDrive/Notes"
BACKUP_DIR="$HOME/Sync/GoogleDrive/Notes_local_backup"
REMOTE="gdrive:Notes"

echo "=== Google Drive Mount Script ==="

# 1. Ensure directories exist
mkdir -p "$LOCAL_DIR"
mkdir -p "$BACKUP_DIR"

# 2. Backup local notes to avoid being hidden by the mount
echo "--> Backing up local notes to $BACKUP_DIR..."
cp -R "$LOCAL_DIR"/* "$BACKUP_DIR/" 2>/dev/null || echo "No local notes found to backup."

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
    if [ "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
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
