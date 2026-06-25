# Notes Sync

A native Linux WYSIWYG notes application built with Python, GTK4, and Libadwaita. Notes are stored as standard Markdown files in a local directory that syncs with Google Drive via rclone.

---

## Features

### Editor
- **Rich text editing** — headings (H1–H3), bold, italic, bullet lists, numbered lists, inline code, and fenced code blocks, all rendered live in the editor
- **Smart list behaviour** — Enter continues a list item with the next number or bullet; Enter on an empty list item exits the list; Backspace at the start converts back to normal text
- **Attachments** — drag-and-drop or button to attach files (PDF, images, ZIP, etc.); displayed as a pill bar below the editor with open and delete buttons; stored in a `.attachments/` subfolder alongside the note
- **Autosave** — saves 2 seconds after typing stops; manual save also available (Ctrl+S)
- **Undo/redo** — full history; tag edits do not clear the undo stack

### Organisation
- **Notebooks** — group notes into subdirectories via a dropdown selector; create and rename notebooks
- **Tags** — YAML front matter tags with per-note editing, a filter dropdown in the sidebar, and a global tag manager (rename/delete a tag across all notes at once)
- **Note pinning** — pin important notes to the top of the list via right-click → Pin; indicated by a pin icon on the row
- **Full-text search** — the sidebar search entry searches note titles and full body content (mtime-cached index; no background daemon required)

### Sync
- **Google Drive sync via rclone** — notes directory is an rclone VFS mount; changes sync automatically while the mount is running
- **Manual sync button** — header bar button triggers `rclone sync` on demand; shows syncing/done/error toast
- **External change detection** — if a note is modified externally (e.g. by a sync), the app reloads it silently or shows a banner if you have unsaved changes

### AI Assistant
- **DeepSeek** handles general queries — summarise, rewrite, search across notes, answer questions about your workspace
- **Gemini** is used for PDF interrogation — when a note has a PDF attachment, check *Ask Gemini about PDF* to query it directly
- Workspace context (note list + contents) is cached in the background so queries are fast even on a network-mounted drive
- Responses stream token-by-token so the first words appear within a couple of seconds
- Configure API keys in **Settings** (gear icon); both keys are stored locally in `~/.config/notes-sync/config.json` and are never committed to the repository

### Import / Export
- Export a single note as Markdown, JSON, or PDF
- Export a notebook or the entire project as a ZIP archive or JSON bundle
- Import notes from Markdown or JSON; import notebooks from ZIP

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+S | Save note |
| Ctrl+N | New note |
| Ctrl+B | Bold |
| Ctrl+I | Italic |
| Ctrl+1 / 2 / 3 | Heading 1 / 2 / 3 |
| Ctrl+8 | Bullet list |
| Ctrl+9 | Numbered list |
| Ctrl+` | Code block |
| Ctrl+0 | Normal paragraph |

---

## Note Format

Notes are plain Markdown files with an optional YAML front matter block:

```markdown
---
tags: [work, ideas]
pinned: true
---
# My Note Title

Body content here...
```

Attachments are referenced as standard Markdown links at the end of the body:

```markdown
[report.pdf](.attachments/report.pdf)
```

---

## Installation

### System dependencies

```bash
sudo apt update
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-markdown rclone fuse3
```

### Clone and run

```bash
git clone https://github.com/firehorse67/notes-sync.git
cd notes-sync
python3 run.py
```

---

## Configuration

### Notes directory and sync command

Edit `notes_app/config.py` to set your notes directory and rclone sync command:

```python
NOTES_DIR = os.path.expanduser("~/Sync/GoogleDrive/Notes/")

# Adjust remote name and path to match your rclone config
# Run `rclone listremotes` to see available remotes
RCLONE_SYNC_CMD = ['rclone', 'sync', NOTES_DIR.rstrip('/'), 'gdrive:Notes', '--quiet']
```

### AI API keys

Open **Settings** (gear icon in the header bar) and enter your API keys:

- **DeepSeek API key** — from [platform.deepseek.com](https://platform.deepseek.com)
- **Gemini API key** — from [aistudio.google.com](https://aistudio.google.com)

Keys are saved to `~/.config/notes-sync/config.json` on your local machine and are never stored in the repository.

---

## Setting up Google Drive Sync

### 1. Configure the rclone remote

```bash
rclone config
```

- Choose **n** (New remote)
- Name it **`gdrive`** (or update `RCLONE_SYNC_CMD` in `config.py` to match your chosen name)
- Type: **`drive`** (Google Drive)
- Leave client\_id and client\_secret blank
- Scope: **`1`** (Full access)
- Auto-config: **y** — a browser window will open to authorise

### 2. Create the remote folder

Create a folder named `Notes` in the root of your Google Drive.

### 3. Mount on login (optional)

Use the included `mount_gdrive.sh` script to mount Google Drive at startup. Add it to your session's Startup Applications with a 5-second delay to allow the network to initialise.

---

## Testing sync

The included `test_sync.sh` script simulates external sync events (new note, new notebook, external edit) to verify that the file monitor and hot-reload logic work correctly:

```bash
./test_sync.sh add-note
./test_sync.sh add-folder
./test_sync.sh modify-active
./test_sync.sh clean
```

---

## License

MIT — see [LICENSE](LICENSE).
