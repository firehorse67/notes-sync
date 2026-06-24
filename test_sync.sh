#!/bin/bash

# Script to simulate Google Drive synchronization updates
# This helps test the Gio.FileMonitor hot-reloading loop.

NOTES_DIR="$HOME/Sync/GoogleDrive/Notes"
mkdir -p "$NOTES_DIR"

echo "=== Google Drive Sync Simulator ==="
echo "Notes folder: $NOTES_DIR"
echo ""

# Function to write a note with tags
write_test_note() {
    local filepath="$1"
    local title="$2"
    local tag="$3"
    
    echo "---" > "$filepath"
    echo "tags: [$tag]" >> "$filepath"
    echo "---" >> "$filepath"
    echo "# $title" >> "$filepath"
    echo "" >> "$filepath"
    echo "This note was generated/modified externally at $(date)." >> "$filepath"
}

case "$1" in
    1|add-note)
        echo "--> Simulating sync: New external note added..."
        write_test_note "$NOTES_DIR/external_sync_test.md" "Synced Note" "sync-demo"
        echo "Done. Created '$NOTES_DIR/external_sync_test.md'."
        echo "Check if 'Synced Note' appears in the app sidebar with tag badge 'sync-demo'."
        ;;
    2|add-folder)
        echo "--> Simulating sync: New external notebook folder added..."
        mkdir -p "$NOTES_DIR/ExternalNotebook"
        echo "Done. Created folder '$NOTES_DIR/ExternalNotebook'."
        echo "Check if 'ExternalNotebook' appears in the Notebooks dropdown in the sidebar."
        ;;
    3|modify-active)
        echo "--> Simulating sync: External edit on hello.md..."
        if [ -f "$NOTES_DIR/hello.md" ]; then
            # We append content
            echo -e "\n- Updated externally at $(date)" >> "$NOTES_DIR/hello.md"
            echo "Done. Appended text to '$NOTES_DIR/hello.md'."
            echo "Check if the app reloads hello.md automatically (or reveals the banner if you had unsaved edits)."
        else
            echo "Error: '$NOTES_DIR/hello.md' does not exist. Please create/open it in the app first."
        fi
        ;;
    4|clean)
        echo "--> Cleaning up simulated sync files..."
        rm -f "$NOTES_DIR/external_sync_test.md"
        rm -rf "$NOTES_DIR/ExternalNotebook"
        echo "Done."
        ;;
    *)
        echo "Usage: ./test_sync.sh [add-note | add-folder | modify-active | clean]"
        echo "Example:"
        echo "  ./test_sync.sh add-note      - Add a new note with tags"
        echo "  ./test_sync.sh add-folder    - Add a new notebook folder"
        echo "  ./test_sync.sh modify-active  - Modify hello.md externally"
        echo "  ./test_sync.sh clean         - Clean up simulation files"
        ;;
esac
