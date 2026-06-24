# Notes Sync

A minimalist, native Linux Markdown notes application built with Python, GTK4, and Libadwaita. It reads and writes native `.md` files in a local directory synced with Google Drive.

## Features

- **Notebook Support**: Group your notes into separate folders (notebooks) with a dedicated dropdown selector.
- **Unified Filter**: Clean dropdown tag filter in the sidebar to view notes containing specific tags.
- **Global Tag Management**: A dedicated **Manage Tags** dialog to rename or delete tags globally across all notes in all notebooks recursively.
- **Native Editor Panel**: Rich text editing with Markdown syntax highlighting powered by `GtkSourceView`.
- **Autosave**: Automatic save triggers 2 seconds after typing stops, plus manual save support.
- **Google Drive Sync Integration**: Active synchronization with Google Drive using `rclone`.
- **System Integration**: Registered under Mint/Accessories menu as **Notes Sync** with a custom desktop launcher and application icon.

---

## Installation & Setup

### Prerequisites

Ensure you have the following system libraries installed (on Ubuntu/Debian/Mint):

```bash
sudo apt update
sudo apt install python3 python3-pip python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 rclone fusermount3
```

---

## Setting up Google Drive Sync with Rclone

To keep your notes synced automatically, set up `rclone` with your Google Drive account.

### 1. Configure the Remote
Run the configuration utility:
```bash
rclone config
```

Follow the prompts:
- Choose **`n`** (New remote).
- Name the remote **`gdrive`** (this exact name is expected by the mount script).
- Type **`drive`** or select the number corresponding to **Google Drive**.
- Leave **client_id** and **client_secret** blank (press Enter).
- Select scope: **`1`** (Full access to all files).
- Leave advanced config at **`n`** (No).
- Choose **`y`** for auto-config. A browser window will open; log into your Google Account and authorize Rclone.
- Confirm and save the configuration.

### 2. Prepare Remote Folder
Create a folder named `Notes` in the root of your Google Drive. Rclone will sync the notes directly to this folder.

### 3. Run the Mount Script
The project includes a mount script `mount_gdrive.sh` that safely backs up any local notes, mounts Google Drive to `~/Sync/GoogleDrive/Notes`, and merges your local notes back.

Make the script executable and run it:
```bash
chmod +x mount_gdrive.sh
./mount_gdrive.sh
```

### 4. Setting up Automatic Launch on Login
To mount Google Drive automatically when you log into your computer:
1. Open the Cinnamon/Mint menu and search for **Startup Applications**.
2. Click the **+** button at the bottom and select **Custom Command**.
3. Fill out the fields:
   - **Name**: Mount Google Drive Notes
   - **Command**: `/home/michael/Linux/Notes/mount_gdrive.sh`
   - **Startup delay**: `5` seconds (gives the network connection time to initialize).
4. Save it.

---

## Running the App

To launch the notes application:

```bash
python3 run.py
```

Or launch it via your system applications menu under **Accessories -> Notes Sync**.
