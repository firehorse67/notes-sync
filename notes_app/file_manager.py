import os
import json
import shutil
import zipfile
import tempfile
from gi.repository import GObject, Gio, GLib
from .config import ensure_notes_dir

class FileManager(GObject.Object):
    __gsignals__ = {
        'files-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'file-loaded': (GObject.SignalFlags.RUN_FIRST, None, (str, str)),  # path, content
        'external-change-detected': (GObject.SignalFlags.RUN_FIRST, None, (bool,)),  # has_unsaved_changes
        'save-status-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),  # "saved", "unsaved", "saving"
        'notebooks-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        GObject.Object.__init__(self)
        self.notes_dir = ensure_notes_dir()
        
        self.active_notebook = None  # None means root notes_dir
        self.active_file_path = None
        self.active_file_mtime = 0
        self.dirty = False
        self.auto_save_enabled = True
        
        self._autosave_timer_id = None
        
        # Dual monitors: 
        # 1. Root monitor for tracking notebooks (subdirs)
        self.root_file = Gio.File.new_for_path(self.notes_dir)
        self.root_monitor = self.root_file.monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self.root_monitor.connect("changed", self._on_root_monitor_changed)
        
        # 2. Active directory monitor for notes
        self.active_monitor = None
        self._update_active_monitor()
        
        # Generate default Markdown Tips note
        self._ensure_markdown_tips_note()

    def _get_active_dir(self):
        """Get path to the currently active directory."""
        if self.active_notebook:
            return os.path.join(self.notes_dir, self.active_notebook)
        return self.notes_dir

    def _update_active_monitor(self):
        """Re-create the active monitor on the current active directory."""
        if self.active_monitor:
            self.active_monitor.cancel()
            self.active_monitor = None
            
        target_dir = self._get_active_dir()
        if os.path.exists(target_dir):
            active_file = Gio.File.new_for_path(target_dir)
            self.active_monitor = active_file.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self.active_monitor.connect("changed", self._on_active_monitor_changed)

    def set_active_notebook(self, notebook):
        """Switch the current notebook."""
        self.cancel_autosave_timer()
        # notebook=None means Root
        self.active_notebook = notebook
        self._update_active_monitor()
        self.emit('files-changed')

    def get_notebooks(self):
        """Get a list of all notebooks (subdirectories)."""
        notebooks = []
        if not os.path.exists(self.notes_dir):
            return notebooks
        try:
            for name in os.listdir(self.notes_dir):
                path = os.path.join(self.notes_dir, name)
                if os.path.isdir(path) and not name.startswith("."):
                    notebooks.append(name)
        except OSError as e:
            print(f"Error listing notebooks: {e}")
        notebooks.sort()
        return notebooks

    def create_notebook(self, name):
        """Create a new notebook folder."""
        safe_name = "".join([c for c in name if c.isalpha() or c.isdigit() or c in ' -_']).strip()
        if not safe_name:
            return False
        path = os.path.join(self.notes_dir, safe_name)
        try:
            os.makedirs(path, exist_ok=True)
            self.emit('notebooks-changed')
            return True
        except OSError as e:
            print(f"Error creating notebook: {e}")
            return False

    def get_files(self):
        """Get all markdown files in the active notebook, sorted by mtime (newest first)."""
        files = []
        target_dir = self._get_active_dir()
        if not os.path.exists(target_dir):
            return files
            
        try:
            for name in os.listdir(target_dir):
                if name.endswith(".md"):
                    path = os.path.join(target_dir, name)
                    try:
                        mtime = os.path.getmtime(path)
                        tags = self.get_tags_for_file(path)
                        files.append({
                            'name': name,
                            'path': path,
                            'mtime': mtime,
                            'tags': tags
                        })
                    except OSError:
                        continue
        except OSError as e:
            print(f"Error listing files: {e}")
            
        files.sort(key=lambda x: x['mtime'], reverse=True)
        return files

    def get_tags_for_file(self, file_path):
        """Parse YAML front matter tags from a note file."""
        tags = []
        if not os.path.exists(file_path):
            return tags
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                # Read up to 15 lines to find front-matter
                lines = []
                for _ in range(15):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line)
                    
            if len(lines) > 0 and lines[0].strip() == "---":
                for line in lines[1:]:
                    line = line.strip()
                    if line == "---":
                        break
                    if line.startswith("tags:"):
                        tags_str = line.split(":", 1)[1].strip()
                        # Bracket format: [tag1, tag2]
                        if tags_str.startswith("[") and tags_str.endswith("]"):
                            tags_str = tags_str[1:-1]
                        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                        break
        except OSError:
            pass
        return tags

    def get_all_tags(self):
        """Get list of all unique tags in the active notebook."""
        tags_set = set()
        for f in self.get_files():
            for tag in f['tags']:
                tags_set.add(tag)
        return sorted(list(tags_set))

    def get_display_title(self, file_path):
        """Read first line of file. If it starts with # header, return it. Otherwise, return filename."""
        if not os.path.exists(file_path):
            return os.path.basename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                # Skip YAML front-matter if present
                first_line = f.readline().strip()
                if first_line == "---":
                    # Read until closing ---
                    while True:
                        line = f.readline()
                        if not line or line.strip() == "---":
                            break
                    # Read next line for the title
                    first_line = f.readline().strip()
                
                if first_line.startswith("#"):
                    title = first_line.lstrip("#").strip()
                    if title:
                        return title
        except OSError:
            pass
        basename = os.path.basename(file_path)
        if basename.endswith(".md"):
            return basename[:-3]
        return basename

    def create_new_note(self, title):
        """Create a new note file in the active notebook."""
        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in ' -_']).strip()
        if not safe_title:
            safe_title = "Untitled"
            
        filename = f"{safe_title}.md"
        target_dir = self._get_active_dir()
        path = os.path.join(target_dir, filename)
        
        counter = 1
        while os.path.exists(path):
            filename = f"{safe_title}_{counter}.md"
            path = os.path.join(target_dir, filename)
            counter += 1
            
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"---\ntags: []\n---\n# {title}\n\n")
            self.emit('files-changed')
            return path
        except OSError as e:
            print(f"Error creating note: {e}")
            return None

    def delete_note(self, path):
        """Delete note file."""
        if not path or not os.path.exists(path):
            return False
        try:
            os.remove(path)
            if self.active_file_path == path:
                self.active_file_path = None
                self.active_file_mtime = 0
                self.dirty = False
                self.cancel_autosave_timer()
                self.emit('save-status-changed', 'saved')
            self.emit('files-changed')
            return True
        except OSError as e:
            print(f"Error deleting note: {e}")
            return False

    def rename_note(self, path, new_title):
        """Rename note file."""
        if not path or not os.path.exists(path):
            return None
        safe_title = "".join([c for c in new_title if c.isalpha() or c.isdigit() or c in ' -_']).strip()
        if not safe_title:
            return None
            
        new_filename = f"{safe_title}.md"
        target_dir = os.path.dirname(path)
        new_path = os.path.join(target_dir, new_filename)
        
        counter = 1
        while os.path.exists(new_path) and new_path != path:
            new_filename = f"{safe_title}_{counter}.md"
            new_path = os.path.join(target_dir, new_filename)
            counter += 1
            
        try:
            os.rename(path, new_path)
            if self.active_file_path == path:
                self.active_file_path = new_path
                self.active_file_mtime = os.path.getmtime(new_path)
            self.emit('files-changed')
            return new_path
        except OSError as e:
            print(f"Error renaming note: {e}")
            return None

    def load_file(self, path):
        """Load note file content into memory."""
        if not os.path.exists(path):
            return False
            
        self.cancel_autosave_timer()
        self.active_file_path = path
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.active_file_mtime = os.path.getmtime(path)
            self.dirty = False
            self.emit('file-loaded', path, content)
            self.emit('save-status-changed', 'saved')
            return True
        except OSError as e:
            print(f"Error loading note: {e}")
            return False

    def save_active_file(self, content):
        """Save content immediately to disk."""
        if not self.active_file_path:
            return False
            
        self.cancel_autosave_timer()
        self.emit('save-status-changed', 'saving')
        
        try:
            with open(self.active_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.active_file_mtime = os.path.getmtime(self.active_file_path)
            self.dirty = False
            self.emit('save-status-changed', 'saved')
            self.emit('files-changed')
            return True
        except OSError as e:
            print(f"Error saving note: {e}")
            self.emit('save-status-changed', 'unsaved')
            return False

    def handle_content_changed(self, get_content_func):
        """Schedule/trigger autosave if enabled when user types."""
        if not self.active_file_path:
            return
            
        if not self.dirty:
            self.dirty = True
            self.emit('save-status-changed', 'unsaved')
            
        self.cancel_autosave_timer()
        
        if self.auto_save_enabled:
            # Schedule autosave in 2 seconds
            self._autosave_timer_id = GLib.timeout_add_seconds(2, self._autosave_callback, get_content_func)

    def cancel_autosave_timer(self):
        if self._autosave_timer_id is not None:
            GLib.source_remove(self._autosave_timer_id)
            self._autosave_timer_id = None

    def _autosave_callback(self, get_content_func):
        self._autosave_timer_id = None
        if self.active_file_path and self.dirty:
            content = get_content_func()
            self.save_active_file(content)
        return GLib.SOURCE_REMOVE

    def _on_root_monitor_changed(self, monitor, file, other_file, event_type):
        """Root monitor detects changes to notebooks (folders)."""
        path = file.get_path()
        if not path:
            return
            
        # If folder created/deleted under notes_dir, notify notebooks change
        if event_type in (Gio.FileMonitorEvent.CREATED, 
                           Gio.FileMonitorEvent.DELETED, 
                           Gio.FileMonitorEvent.MOVED,
                           Gio.FileMonitorEvent.MOVED_IN,
                           Gio.FileMonitorEvent.MOVED_OUT):
            if os.path.isdir(path) or event_type == Gio.FileMonitorEvent.DELETED:
                GLib.idle_add(self.emit, 'notebooks-changed')

    def _on_active_monitor_changed(self, monitor, file, other_file, event_type):
        """Active monitor detects changes to notes within active notebook."""
        path = file.get_path()
        if not path:
            return

        if event_type in (Gio.FileMonitorEvent.CREATED, 
                           Gio.FileMonitorEvent.DELETED, 
                           Gio.FileMonitorEvent.MOVED,
                           Gio.FileMonitorEvent.MOVED_IN,
                           Gio.FileMonitorEvent.MOVED_OUT):
            GLib.idle_add(self.emit, 'files-changed')
            
        elif path == self.active_file_path and event_type in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CHANGED):
            if not os.path.exists(path):
                return
            try:
                new_mtime = os.path.getmtime(path)
            except OSError:
                return

            if new_mtime > self.active_file_mtime:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        disk_content = f.read()
                except OSError:
                    return

                GLib.idle_add(self._check_external_change, new_mtime, disk_content)

    def _check_external_change(self, new_mtime, disk_content):
        if not self.active_file_path:
            return
            
        if not self.dirty:
            self.active_file_mtime = new_mtime
            self.emit('file-loaded', self.active_file_path, disk_content)
        else:
            self.emit('external-change-detected', True)

    def _ensure_markdown_tips_note(self):
        path = os.path.join(self.notes_dir, "Markdown Tips.md")
        if not os.path.exists(path):
            try:
                tips_content = """---
tags: [markdown, documentation, help]
---
# Markdown Code Tips

Welcome to your Markdown Notes App! Here are some common Markdown syntax tips to help you write notes.

## Text Formatting
- **Bold text**: Wrap text in `**double asterisks**`
- *Italic text*: Wrap text in `*single asterisks*` or `_underscores_`
- ~~Strikethrough~~: Wrap text in `~~double tildes~~`

## Headings
Use `#` symbols at the start of a line:
# Heading 1
## Heading 2
### Heading 3

## Lists
### Unordered List:
- Item A
- Item B
  - Sub-item B1

### Ordered List:
1. First item
2. Second item

## Code Blocks
Inline code is wrapped in backticks like `this`.

For blocks of code, use triple backticks:
```python
def hello_world():
    print("Hello from GTK4 Markdown Notes App!")
```

## Tables
| Feature | Supported | Native |
|---|---|---|
| Auto-save | Yes | Yes |
| Notebooks | Yes | Yes |
| YAML Tags | Yes | Yes |

## Links and Images
- [Google](https://google.com)
- Image: `![Alt Text](URL)`
"""
                with open(path, "w", encoding="utf-8") as f:
                    f.write(tips_content)
            except OSError as e:
                print(f"Error creating Markdown tips: {e}")

    def rename_notebook(self, old_name, new_name):
        """Rename a notebook subdirectory."""
        if not old_name:
            return False
        safe_new_name = "".join([c for c in new_name if c.isalpha() or c.isdigit() or c in ' -_']).strip()
        if not safe_new_name:
            return False
            
        old_path = os.path.join(self.notes_dir, old_name)
        new_path = os.path.join(self.notes_dir, safe_new_name)
        
        if not os.path.exists(old_path) or os.path.exists(new_path):
            return False
            
        try:
            os.rename(old_path, new_path)
            if self.active_notebook == old_name:
                self.active_notebook = safe_new_name
                self._update_active_monitor()
            self.emit('notebooks-changed')
            self.emit('files-changed')
            return True
        except OSError as e:
            print(f"Error renaming notebook: {e}")
            return False

    def move_note(self, path, target_notebook):
        """Move a note file to a different notebook."""
        if not path or not os.path.exists(path):
            return None
            
        filename = os.path.basename(path)
        # target_notebook == "" means root
        if target_notebook:
            target_dir = os.path.join(self.notes_dir, target_notebook)
        else:
            target_dir = self.notes_dir
            
        if not os.path.exists(target_dir):
            return None
            
        new_path = os.path.join(target_dir, filename)
        
        # Avoid collisions
        counter = 1
        base, ext = os.path.splitext(filename)
        while os.path.exists(new_path):
            new_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
            counter += 1
            
        try:
            os.rename(path, new_path)
            if self.active_file_path == path:
                self.active_file_path = new_path
                self.active_file_mtime = os.path.getmtime(new_path)
            self.emit('files-changed')
            return new_path
        except OSError as e:
            print(f"Error moving note: {e}")
            return None

    def update_tags_for_file(self, file_path, tags):
        """Update YAML front matter tags in the markdown file."""
        if not os.path.exists(file_path):
            return False
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            lines = content.splitlines()
            
            has_front_matter = False
            fm_end_index = -1
            tags_line_index = -1
            
            if len(lines) > 0 and lines[0].strip() == "---":
                for i in range(1, min(len(lines), 15)):
                    line = lines[i].strip()
                    if line == "---":
                        has_front_matter = True
                        fm_end_index = i
                        break
                    if line.startswith("tags:"):
                        tags_line_index = i
                        
            tags_str = ", ".join(tags)
            new_tags_line = f"tags: [{tags_str}]"
            
            self.cancel_autosave_timer()
            
            if has_front_matter:
                if tags_line_index != -1:
                    lines[tags_line_index] = new_tags_line
                else:
                    lines.insert(fm_end_index, new_tags_line)
            else:
                lines.insert(0, "---")
                lines.insert(1, new_tags_line)
                lines.insert(2, "---")
                
            new_content = "\n".join(lines) + "\n"
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
                
            self.active_file_mtime = os.path.getmtime(file_path)
            
            self.emit('files-changed')
            self.emit('file-loaded', file_path, new_content)
            return True
        except OSError as e:
            print(f"Error updating tags: {e}")
            return False

    def rename_tag_globally(self, old_tag, new_tag):
        """Rename a tag globally across all markdown files in all notebooks."""
        old_tag = old_tag.strip().lower()
        new_tag = new_tag.strip().lower()
        if not old_tag or not new_tag or old_tag == new_tag:
            return False
            
        modified_any = False
        active_modified = False
        
        for root, dirs, files in os.walk(self.notes_dir):
            for filename in files:
                if filename.endswith(".md"):
                    path = os.path.join(root, filename)
                    tags = self.get_tags_for_file(path)
                    
                    normalized_tags = [t.lower() for t in tags]
                    if old_tag in normalized_tags:
                        updated_tags = []
                        for t in tags:
                            if t.lower() == old_tag:
                                if new_tag not in [ut.lower() for ut in updated_tags]:
                                    updated_tags.append(new_tag)
                            else:
                                updated_tags.append(t)
                                
                        self.update_tags_for_file(path, updated_tags)
                        modified_any = True
                        if path == self.active_file_path:
                            active_modified = True
                            
        if modified_any:
            self.emit('files-changed')
            if active_modified and self.active_file_path:
                try:
                    with open(self.active_file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.emit('file-loaded', self.active_file_path, content)
                except OSError:
                    pass
        return modified_any

    def delete_tag_globally(self, tag_to_delete):
        """Delete a tag globally from all markdown notes in all notebooks."""
        tag_to_delete = tag_to_delete.strip().lower()
        if not tag_to_delete:
            return False
            
        modified_any = False
        active_modified = False
        
        for root, dirs, files in os.walk(self.notes_dir):
            for filename in files:
                if filename.endswith(".md"):
                    path = os.path.join(root, filename)
                    tags = self.get_tags_for_file(path)
                    
                    normalized_tags = [t.lower() for t in tags]
                    if tag_to_delete in normalized_tags:
                        updated_tags = [t for t in tags if t.lower() != tag_to_delete]
                        self.update_tags_for_file(path, updated_tags)
                        modified_any = True
                        if path == self.active_file_path:
                            active_modified = True
                            
        if modified_any:
            self.emit('files-changed')
            if active_modified and self.active_file_path:
                try:
                    with open(self.active_file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.emit('file-loaded', self.active_file_path, content)
                except OSError:
                    pass
        return modified_any

    # --- Import / Export Core Methods ---
    def get_note_as_dict(self, file_path):
        """Read a note and return its content and tags as a dictionary."""
        try:
            if not os.path.exists(file_path):
                return None
                
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            content_start_line = 0
            if len(lines) > 0 and lines[0].strip() == "---":
                for i in range(1, len(lines)):
                    if lines[i].strip() == "---":
                        content_start_line = i + 1
                        break
                        
            content = "".join(lines[content_start_line:])
            tags = self.get_tags_for_file(file_path)
            title = self.get_display_title(file_path)
            # Relative path to keep structure
            rel_path = os.path.relpath(file_path, self.notes_dir)
            return {
                "title": title,
                "tags": tags,
                "content": content,
                "relative_path": rel_path
            }
        except Exception as e:
            print(f"Error reading note as dict {file_path}: {e}")
            return None


    def export_note_to_markdown(self, note_path, dest_path):
        """Copy the raw markdown file to a destination path."""
        try:
            shutil.copy2(note_path, dest_path)
            return True
        except Exception as e:
            print(f"Error exporting note to markdown: {e}")
            return False

    def export_note_to_json(self, note_path, dest_path):
        """Serialize a note's metadata and content to a JSON file."""
        try:
            data = self.get_note_as_dict(note_path)
            if data:
                with open(dest_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                return True
        except Exception as e:
            print(f"Error exporting note to json: {e}")
        return False

    def import_note_from_markdown(self, src_path, target_notebook=None):
        """Import an external markdown file into the notes directory/notebook."""
        try:
            # Determine filename
            basename = os.path.basename(src_path)
            name, _ = os.path.splitext(basename)
            
            # Destination path
            target_dir = self.notes_dir if not target_notebook else os.path.join(self.notes_dir, target_notebook)
            os.makedirs(target_dir, exist_ok=True)
            
            dest_path = os.path.join(target_dir, basename)
            # Avoid overwriting; append number if exists
            counter = 1
            while os.path.exists(dest_path):
                dest_path = os.path.join(target_dir, f"{name}_{counter}.md")
                counter += 1
                
            shutil.copy2(src_path, dest_path)
            self.emit('files-changed')
            return True
        except Exception as e:
            print(f"Error importing markdown note: {e}")
            return False

    def import_note_from_json(self, src_path, target_notebook=None):
        """Import a note from a JSON file."""
        try:
            with open(src_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            title = data.get("title", "Imported Note")
            tags = data.get("tags", [])
            content = data.get("content", "")
            
            target_dir = self.notes_dir if not target_notebook else os.path.join(self.notes_dir, target_notebook)
            os.makedirs(target_dir, exist_ok=True)
            
            # Find unique file path
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()
            if not safe_title:
                safe_title = "Imported Note"
            dest_path = os.path.join(target_dir, f"{safe_title}.md")
            counter = 1
            while os.path.exists(dest_path):
                dest_path = os.path.join(target_dir, f"{safe_title}_{counter}.md")
                counter += 1
                
            # Write note markdown file
            with open(dest_path, 'w', encoding='utf-8') as f:
                # Write front matter if tags present
                if tags:
                    f.write("---\n")
                    f.write(f"tags: [{', '.join(tags)}]\n")
                    f.write("---\n")
                f.write(content)
                
            self.emit('files-changed')
            return True
        except Exception as e:
            print(f"Error importing json note: {e}")
            return False

    def export_notebook_to_zip(self, notebook_name, dest_path):
        """Export a single notebook directory as a ZIP archive of markdown files."""
        try:
            notebook_dir = self.notes_dir if not notebook_name else os.path.join(self.notes_dir, notebook_name)
            if not os.path.exists(notebook_dir):
                return False
                
            with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in os.listdir(notebook_dir):
                    if file.endswith('.md'):
                        full_path = os.path.join(notebook_dir, file)
                        zipf.write(full_path, file)
            return True
        except Exception as e:
            print(f"Error exporting notebook to zip: {e}")
            return False

    def export_notebook_to_json(self, notebook_name, dest_path):
        """Export all notes in a single notebook to a single JSON archive."""
        try:
            data = self.get_notebook_as_dict(notebook_name)
            with open(dest_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error exporting notebook to json: {e}")
            return False

    def get_notebook_as_dict(self, notebook_name):
        notebook_dir = self.notes_dir if not notebook_name else os.path.join(self.notes_dir, notebook_name)
        notes = []
        if os.path.exists(notebook_dir):
            for file in os.listdir(notebook_dir):
                if file.endswith('.md'):
                    full_path = os.path.join(notebook_dir, file)
                    note_data = self.get_note_as_dict(full_path)
                    if note_data:
                        notes.append(note_data)
        return {
            "notebook": notebook_name or "Root",
            "notes": notes
        }

    def export_project_to_zip(self, dest_path):
        """Export all notebooks and root notes as a nested ZIP of markdown files."""
        try:
            with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.notes_dir):
                    # Skip hidden directories like .git
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for file in files:
                        if file.endswith('.md'):
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, self.notes_dir)
                            zipf.write(full_path, rel_path)
            return True
        except Exception as e:
            print(f"Error exporting project to zip: {e}")
            return False

    def export_project_to_json(self, dest_path):
        """Export the entire workspace to a single nested JSON backup file."""
        try:
            project_data = {
                "version": "1.0",
                "root_notes": [],
                "notebooks": []
            }
            # Root notes
            for file in os.listdir(self.notes_dir):
                full_path = os.path.join(self.notes_dir, file)
                if os.path.isfile(full_path) and file.endswith('.md'):
                    note_data = self.get_note_as_dict(full_path)
                    if note_data:
                        project_data["root_notes"].append(note_data)
                        
            # Notebook subdirectories
            for notebook in self.get_notebooks():
                notebook_data = self.get_notebook_as_dict(notebook)
                project_data["notebooks"].append(notebook_data)
                
            with open(dest_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error exporting project to json: {e}")
            return False

    def import_notebook_from_zip(self, src_path):
        """Extract a ZIP archive of markdown files and merge into active notebook or workspace."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(src_path, 'r') as zipf:
                    zipf.extractall(tmpdir)
                
                # Walk extracted files and import them
                imported_any = False
                for root, dirs, files in os.walk(tmpdir):
                    for file in files:
                        if file.endswith('.md'):
                            # Figure out relative notebook path
                            rel_dir = os.path.relpath(root, tmpdir)
                            notebook_target = None if rel_dir == '.' else rel_dir
                            
                            src_file = os.path.join(root, file)
                            if self.import_note_from_markdown(src_file, notebook_target):
                                imported_any = True
                
                if imported_any:
                    self.emit('notebooks-changed')
                    self.emit('files-changed')
                return imported_any
        except Exception as e:
            print(f"Error importing from zip: {e}")
            return False

    def import_project_from_json(self, src_path):
        """Restore all notebooks and notes from a single JSON project backup."""
        try:
            with open(src_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            imported_any = False
            
            # Helper to write a note dict
            def import_dict_note(note_data, notebook_name):
                title = note_data.get("title", "Imported Note")
                tags = note_data.get("tags", [])
                content = note_data.get("content", "")
                
                target_dir = self.notes_dir if not notebook_name else os.path.join(self.notes_dir, notebook_name)
                os.makedirs(target_dir, exist_ok=True)
                
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()
                if not safe_title:
                    safe_title = "Imported Note"
                dest_path = os.path.join(target_dir, f"{safe_title}.md")
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(target_dir, f"{safe_title}_{counter}.md")
                    counter += 1
                
                with open(dest_path, 'w', encoding='utf-8') as nf:
                    if tags:
                        nf.write("---\n")
                        nf.write(f"tags: [{', '.join(tags)}]\n")
                        nf.write("---\n")
                    nf.write(content)
                return True

            # Import root notes
            for note_data in data.get("root_notes", []):
                if import_dict_note(note_data, None):
                    imported_any = True
                    
            # Import notebooks
            for notebook_data in data.get("notebooks", []):
                notebook_name = notebook_data.get("notebook")
                if notebook_name == "Root":
                    notebook_name = None
                for note_data in notebook_data.get("notes", []):
                    if import_dict_note(note_data, notebook_name):
                        imported_any = True
                        
            if imported_any:
                self.emit('notebooks-changed')
                self.emit('files-changed')
            return imported_any
        except Exception as e:
            print(f"Error importing project from json: {e}")
            return False

