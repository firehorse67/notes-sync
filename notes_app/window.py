import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, GObject, Gdk
from .sidebar import SidebarView
from .editor import MarkdownEditor
import os

class EditTagsDialog(Gtk.Dialog):
    def __init__(self, parent, current_tags):
        super().__init__(title="Edit Tags", transient_for=parent, modal=True)
        self.set_default_size(320, -1)
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Save", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        
        content = self.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        
        label = Gtk.Label(label="Edit tags (comma-separated):")
        label.set_halign(Gtk.Align.START)
        content.append(label)
        
        self.entry = Gtk.Entry()
        self.entry.set_text(", ".join(current_tags))
        self.entry.set_activates_default(True)
        content.append(self.entry)
        self.entry.grab_focus()

    def get_tags(self):
        raw = self.entry.get_text()
        return [t.strip().lower() for t in raw.split(",") if t.strip()]


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, file_manager):
        super().__init__(application=app)
        self.set_title("Notes")
        self.set_default_size(850, 600)
        
        self.file_manager = file_manager
        
        # Load custom CSS styles globally
        self._load_custom_css()
        
        # Setup Toast Overlay
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)
        
        # Navigation Split View
        self.split_view = Adw.NavigationSplitView()
        self.toast_overlay.set_child(self.split_view)
        
        # --- Sidebar Navigation Page ---
        self.sidebar = SidebarView(self.file_manager)
        self.sidebar.connect("note-selected", self._on_note_selected)
        self.sidebar.connect("create-note", self._on_create_note)
        self.sidebar.connect("delete-note", self._on_delete_note)
        self.sidebar.connect("rename-note", self._on_rename_note)
        self.sidebar.connect("notebook-changed", self._on_notebook_changed)
        self.sidebar.connect("move-note", self._on_move_note)
        self.sidebar.connect("rename-tag-global", self._on_rename_tag_global)
        self.sidebar.connect("delete-tag-global", self._on_delete_tag_global)
        self.sidebar.connect("pin-note", self._on_pin_note)
        
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.get_style_context().add_class("sidebar-container")
        sidebar_header = Adw.HeaderBar()
        sidebar_header.get_style_context().add_class("nav-bar-blue")
        sidebar_box.append(sidebar_header)
        sidebar_box.append(self.sidebar)
        
        sidebar_page = Adw.NavigationPage.new(sidebar_box, "Notes")
        self.split_view.set_sidebar(sidebar_page)
        
        # --- Content Navigation Page ---
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Header bar for editor
        self.content_header = Adw.HeaderBar()
        self.content_header.get_style_context().add_class("nav-bar-blue")
        content_box.append(self.content_header)
        
        # Header bar controls (packed from right to left)
        # 1. Status Label ("Saved" / "Unsaved" / "Saving...")
        self.status_label = Gtk.Label(label="Saved")
        self.status_label.get_style_context().add_class("dim-label")
        self.status_label.set_margin_end(12)
        self.content_header.pack_end(self.status_label)

        # 1b. Word count label
        self.word_count_label = Gtk.Label(label="")
        self.word_count_label.get_style_context().add_class("dim-label")
        self.word_count_label.set_margin_end(12)
        self.content_header.pack_end(self.word_count_label)
        
        # 2. Auto-save toggle switch with label
        autosave_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        autosave_box.set_valign(Gtk.Align.CENTER)
        autosave_box.set_margin_end(12)
        
        autosave_lbl = Gtk.Label(label="Auto-save")
        autosave_lbl.get_style_context().add_class("dim-label")
        autosave_box.append(autosave_lbl)
        
        self.autosave_switch = Gtk.Switch()
        self.autosave_switch.set_active(True)
        self.autosave_switch.connect("notify::active", self._on_autosave_active)
        autosave_box.append(self.autosave_switch)
        
        self.content_header.pack_end(autosave_box)
        
        # 3. Manual Save Button
        self.save_button = Gtk.Button.new_from_icon_name("document-save-symbolic")
        self.save_button.set_tooltip_text("Save Note (Ctrl+S)")
        self.save_button.connect("clicked", self._on_save_clicked)
        self.save_button.set_sensitive(False)  # Disabled initially
        self.content_header.pack_end(self.save_button)
        
        # 4. Edit Tags Button
        self.tags_button = Gtk.Button.new_from_icon_name("tag-symbolic")
        self.tags_button.set_tooltip_text("Edit Tags")
        self.tags_button.connect("clicked", self._on_edit_tags_clicked)
        self.tags_button.set_sensitive(True)
        self.content_header.pack_end(self.tags_button)
        
        # 4b. Import/Export Button
        self.transfer_button = Gtk.MenuButton()
        self.transfer_button.set_icon_name("document-send-symbolic")
        self.transfer_button.set_tooltip_text("Import/Export Note")
        
        transfer_popover = Gtk.Popover()
        transfer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        transfer_box.set_margin_start(6)
        transfer_box.set_margin_end(6)
        transfer_box.set_margin_top(6)
        transfer_box.set_margin_bottom(6)
        
        exp_md_btn = Gtk.Button(label="Export as Markdown (.md)...")
        exp_md_btn.set_has_frame(False)
        exp_md_btn.connect("clicked", self._on_export_markdown_clicked, transfer_popover)
        transfer_box.append(exp_md_btn)
        
        exp_json_btn = Gtk.Button(label="Export as JSON (.json)...")
        exp_json_btn.set_has_frame(False)
        exp_json_btn.connect("clicked", self._on_export_json_clicked, transfer_popover)
        transfer_box.append(exp_json_btn)
        
        exp_pdf_btn = Gtk.Button(label="Export as PDF (.pdf)...")
        exp_pdf_btn.set_has_frame(False)
        exp_pdf_btn.connect("clicked", self._on_export_pdf_clicked, transfer_popover)
        transfer_box.append(exp_pdf_btn)

        imp_md_btn = Gtk.Button(label="Import from Markdown (.md)...")
        imp_md_btn.set_has_frame(False)
        imp_md_btn.connect("clicked", self._on_import_markdown_clicked, transfer_popover)
        transfer_box.append(imp_md_btn)
        
        imp_json_btn = Gtk.Button(label="Import from JSON (.json)...")
        imp_json_btn.set_has_frame(False)
        imp_json_btn.connect("clicked", self._on_import_json_clicked, transfer_popover)
        transfer_box.append(imp_json_btn)
        
        transfer_popover.set_child(transfer_box)
        self.transfer_button.set_popover(transfer_popover)
        self.content_header.pack_end(self.transfer_button)
        
        # 5. Delete Button
        self.delete_button = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        self.delete_button.set_tooltip_text("Delete Note")
        self.delete_button.get_style_context().add_class("destructive-action")
        self.delete_button.connect("clicked", self._on_header_delete_clicked)
        self.delete_button.set_sensitive(True)
        self.content_header.pack_end(self.delete_button)

        # Sync button (left side of header)
        self.sync_button = Gtk.Button.new_from_icon_name("emblem-synchronizing-symbolic")
        self.sync_button.set_tooltip_text("Sync with Google Drive")
        self.sync_button.connect("clicked", self._on_sync_clicked)
        self.content_header.pack_start(self.sync_button)
        
        # External modification banner
        self.banner = Adw.Banner()
        self.banner.set_title("This note has been modified externally.")
        self.banner.set_button_label("Reload")
        self.banner.connect("button-clicked", self._on_reload_banner_clicked)
        content_box.append(self.banner)
        
        # Stack to switch between Editor and Empty State
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        content_box.append(self.stack)
        
        # Empty state page
        self.status_page = Adw.StatusPage()
        self.status_page.set_title("No Note Selected")
        self.status_page.set_description("Select a note from the list or create a new one.")
        self.status_page.set_icon_name("document-open-symbolic")
        self.stack.add_named(self.status_page, "empty")
        
        # Editor page
        self.editor = MarkdownEditor()
        self.editor.connect("content-changed", self._on_editor_changed)
        self.stack.add_named(self.editor, "editor")
        
        self.stack.set_visible_child_name("empty")
        
        self.content_page = Adw.NavigationPage.new(content_box, "")
        self.split_view.set_content(self.content_page)
        
        # Hide controls when no note is loaded
        self._set_editor_controls_visible(False)
        
        # --- File Manager Listeners ---
        self.file_manager.connect("files-changed", self._on_files_changed)
        self.file_manager.connect("file-loaded", self._on_file_loaded)
        self.file_manager.connect("external-change-detected", self._on_external_change_detected)
        self.file_manager.connect("save-status-changed", self._on_save_status_changed)
        self.file_manager.connect("note-saved", self._on_note_saved)
        self.file_manager.connect("sync-status-changed", self._on_sync_status_changed)
        
        # Populate sidebar on load
        self.sidebar.populate()
        
        # Setup actions and keyboard shortcuts
        self._setup_actions()

    def _load_custom_css(self):
        """Inject custom CSS for tag pills, dimmer labels, blue header bars, and soft yellow sidebar."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            /* Blue Header Bars (Top Nav Bars) */
            .nav-bar-blue, headerbar {
                background-color: #1e3a8a; /* Deep dark blue */
                color: #ffffff;
            }
            .nav-bar-blue label, .nav-bar-blue button, headerbar label, headerbar button {
                color: #ffffff;
            }
            .nav-bar-blue image, headerbar image {
                color: #ffffff;
            }

            /* Destructive button (Delete) */
            button.destructive-action {
                background-color: #ef4444;
                color: #ffffff;
            }
            button.destructive-action:hover {
                background-color: #dc2626;
            }

            /* Soft Yellow Sidebar */
            .sidebar-container {
                background-color: #fef9c3; /* Soft yellow (yellow-100) */
            }
            /* Make the note ListBox transparent to let yellow show through */
            .sidebar-container list {
                background-color: transparent;
            }
            .sidebar-container row {
                background-color: transparent;
                border-bottom: 1px solid rgba(0, 0, 0, 0.05);
            }
            .sidebar-container row:hover {
                background-color: rgba(0, 0, 0, 0.04);
            }
            .sidebar-container row:selected {
                background-color: rgba(30, 58, 138, 0.12); /* Blue selection highlight */
                color: inherit;
            }
            
            /* Make search entries and dropdowns transparent-yellow styled */
            .sidebar-container entry, .sidebar-container dropdown, .sidebar-container button {
                background-color: rgba(255, 255, 255, 0.5);
                border: 1px solid rgba(0, 0, 0, 0.1);
            }

            /* Reset color inheritance inside popovers so buttons are readable */
            popover label, popover button label {
                color: #1f2937;
            }

            /* Tag Pills */
            .tag-pill {
                background-color: rgba(30, 58, 138, 0.08); /* Light blue tint */
                color: #1e3a8a;
                border-radius: 8px;
                padding-left: 8px;
                padding-right: 8px;
                padding-top: 2px;
                padding-bottom: 2px;
                font-size: 8pt;
                font-weight: bold;
            }
            .dim-label {
                opacity: 0.65;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _setup_actions(self):
        """Set up actions like Save (Ctrl+S) and New Note (Ctrl+N)."""
        save_action = Gio.SimpleAction.new("save", None)
        save_action.connect("activate", self._on_save_shortcut)
        self.add_action(save_action)

        new_note_action = Gio.SimpleAction.new("new-note", None)
        new_note_action.connect("activate", lambda a, p: self.sidebar._on_add_clicked(None))
        self.add_action(new_note_action)

        app = self.get_application()
        app.set_accels_for_action("win.save", ["<Control>s"])
        app.set_accels_for_action("win.new-note", ["<Control>n"])

    def _set_editor_controls_visible(self, visible):
        """Show or hide the header save/autosave controls."""
        self.status_label.set_visible(visible)
        self.word_count_label.set_visible(visible)
        self.autosave_switch.get_parent().set_visible(visible)  # Box container
        self.save_button.set_visible(visible)
        self.tags_button.set_visible(visible)
        self.transfer_button.set_visible(visible)
        self.delete_button.set_visible(visible)

    # --- Action Handlers ---
    def _on_save_shortcut(self, action, param):
        self._perform_manual_save()

    def _on_save_clicked(self, button):
        self._perform_manual_save()

    def _perform_manual_save(self):
        if self.file_manager.active_file_path and self.file_manager.dirty:
            content = self.editor.get_content()
            def on_done(success):
                if success:
                    self._show_toast("Note saved")
                    self.banner.set_revealed(False)
                    self.sidebar.populate()
            self.file_manager.save_active_file(content, on_complete=on_done, get_content_func=self.editor.get_content)

    def _show_toast(self, text):
        toast = Adw.Toast.new(text)
        self.toast_overlay.add_toast(toast)

    # --- UI Event Handlers ---
    def _on_note_selected(self, sidebar, file_path):
        self.banner.set_revealed(False)
        if file_path:
            self.file_manager.load_file(file_path)
            self._set_editor_controls_visible(True)

    def _on_create_note(self, sidebar, title):
        new_path = self.file_manager.create_new_note(title)
        if new_path:
            self._show_toast(f"Created note '{title}'")
            self.sidebar.populate()
            self._select_row_by_path(new_path)

    def _on_delete_note(self, sidebar, file_path):
        title = self.file_manager.get_display_title(file_path)
        if self.file_manager.delete_note(file_path):
            self._show_toast(f"Deleted note '{title}'")
            self.sidebar.populate()
            if not self.file_manager.active_file_path:
                self.stack.set_visible_child_name("empty")
                self.content_page.set_title("")
                self._set_editor_controls_visible(False)

    def _on_header_delete_clicked(self, button):
        if self.file_manager.active_file_path:
            self._on_delete_note(self.sidebar, self.file_manager.active_file_path)

    def _on_edit_tags_clicked(self, button):
        path = self.file_manager.active_file_path
        if not path:
            return
        current_tags = self.file_manager.get_tags_for_file(path)
        dialog = EditTagsDialog(self, current_tags)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                tags = dialog.get_tags()
                self.file_manager.update_tags_for_file(path, tags)
                self._show_toast("Tags updated")
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_move_note(self, sidebar, file_path, target_notebook):
        new_path = self.file_manager.move_note(file_path, target_notebook)
        if new_path:
            target_name = target_notebook if target_notebook else "All Notes"
            title = self.file_manager.get_display_title(new_path)
            self._show_toast(f"Moved '{title}' to '{target_name}'")
            if self.file_manager.active_file_path == new_path:
                self.stack.set_visible_child_name("empty")
                self.content_page.set_title("")
                self._set_editor_controls_visible(False)
            self.sidebar.populate()

    def _on_rename_note(self, sidebar, file_path, new_title):
        old_title = self.file_manager.get_display_title(file_path)
        new_path = self.file_manager.rename_note(file_path, new_title)
        if new_path:
            self._show_toast(f"Renamed '{old_title}' to '{new_title}'")
            self.sidebar.populate()
            self._select_row_by_path(new_path)

    def _update_word_count(self):
        import re
        content = self.editor.get_content()
        # Strip fenced code blocks, then markdown tokens, then count words
        text = re.sub(r'```[\s\S]*?```', ' ', content)
        text = re.sub(r'`[^`]+`', ' ', text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'~~(.+?)~~', r'\1', text)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'^[-*+>]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\d+[.)]\s+', '', text, flags=re.MULTILINE)
        words = len(text.split())
        self.word_count_label.set_label(f"{words:,} words")

    def _on_editor_changed(self, editor):
        self.file_manager.handle_content_changed(self.editor.get_content)
        self._update_word_count()

    def _on_reload_banner_clicked(self, banner):
        self.banner.set_revealed(False)
        if self.file_manager.active_file_path:
            self.file_manager.load_file(self.file_manager.active_file_path)
            self._show_toast("Reloaded from disk")

    def _on_autosave_active(self, switch, pspec):
        active = switch.get_active()
        self.file_manager.auto_save_enabled = active
        if not active:
            self.file_manager.cancel_autosave_timer()
            # If currently dirty, enable manual save
            if self.file_manager.dirty:
                self.save_button.set_sensitive(True)
                self.status_label.set_text("Unsaved")
        else:
            # If auto-save is enabled and dirty, save immediately
            if self.file_manager.dirty:
                self._perform_manual_save()

    def _on_notebook_changed(self, sidebar, notebook_name):
        """Fires when the active notebook is changed in the sidebar."""
        # Unload active note since it belongs to the previous notebook
        self.stack.set_visible_child_name("empty")
        self.content_page.set_title("")
        self._set_editor_controls_visible(False)
        self.file_manager.active_file_path = None
        self.file_manager.active_file_mtime = 0
        self.file_manager.dirty = False
        self.banner.set_revealed(False)
        self.editor.active_file_path = None

    # --- File Manager Signaled Events ---
    def _on_files_changed(self, file_manager):
        self.sidebar.populate()

    def _on_note_saved(self, file_manager, path, title, mtime):
        self.sidebar.update_note_row(path, title, mtime)

    def _on_file_loaded(self, file_manager, path, content):
        title = self.file_manager.get_display_title(path)
        self.editor.set_content(content, path)
        self.content_page.set_title(title)
        self.stack.set_visible_child_name("editor")
        self.editor.set_editable(True)
        self.banner.set_revealed(False)
        self._set_editor_controls_visible(True)
        self._update_word_count()

        # Reset Save button state (fully saved on load)
        self.save_button.set_sensitive(False)
        self.status_label.set_text("Saved")
        
        self.split_view.set_show_content(True)

    def _on_external_change_detected(self, file_manager, has_unsaved_changes):
        if has_unsaved_changes:
            self.banner.set_revealed(True)
        else:
            self._show_toast("Note reloaded from external change")

    def _on_save_status_changed(self, file_manager, status):
        """Syncs the header bar label and manual save button with save states."""
        if status == "saved":
            self.status_label.set_text("Saved")
            self.save_button.set_sensitive(False)
        elif status == "unsaved":
            self.status_label.set_text("Unsaved")
            self.save_button.set_sensitive(True)
        elif status == "saving":
            self.status_label.set_text("Saving...")
            self.save_button.set_sensitive(False)

    # --- Helpers ---
    def _select_row_by_path(self, path):
        row = self.sidebar.list_box.get_first_child()
        while row:
            if hasattr(row, 'file_path') and row.file_path == path:
                self.sidebar.list_box.select_row(row)
                break
            row = row.get_next_sibling()

    def _on_pin_note(self, sidebar, file_path, pinned):
        if self.file_manager.pin_note(file_path, pinned):
            title = self.file_manager.get_display_title(file_path)
            action = "Pinned" if pinned else "Unpinned"
            self._show_toast(f"{action} '{title}'")

    def _on_sync_clicked(self, button):
        self.file_manager.trigger_sync()

    def _on_sync_status_changed(self, file_manager, status):
        if status == 'syncing':
            self.sync_button.set_sensitive(False)
            self._show_toast("Syncing with Google Drive...")
        elif status == 'done':
            self.sync_button.set_sensitive(True)
            self._show_toast("Sync complete")
        elif status == 'error':
            self.sync_button.set_sensitive(True)
            self._show_toast("Sync failed — check rclone config")

    def _on_rename_tag_global(self, sidebar, old_tag, new_tag):
        if self.file_manager.rename_tag_globally(old_tag, new_tag):
            self._show_toast(f"Renamed tag '{old_tag}' to '{new_tag}' globally")
            self.sidebar.populate()

    def _on_delete_tag_global(self, sidebar, tag):
        if self.file_manager.delete_tag_globally(tag):
            self._show_toast(f"Deleted tag '{tag}' globally")
            self.sidebar.populate()

    # --- Note Import / Export Handlers ---
    def _on_export_markdown_clicked(self, btn, popover):
        popover.popdown()
        if not self.file_manager.active_file_path:
            return
            
        dialog = Gtk.FileChooserNative(
            title="Export Note to Markdown",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Export",
            cancel_label="Cancel"
        )
        title = self.file_manager.get_display_title(self.file_manager.active_file_path)
        dialog.set_current_name(f"{title}.md")
        
        filter_md = Gtk.FileFilter()
        filter_md.set_name("Markdown files (*.md)")
        filter_md.add_pattern("*.md")
        dialog.add_filter(filter_md)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                dest = dialog.get_file().get_path()
                if self.file_manager.export_note_to_markdown(self.file_manager.active_file_path, dest):
                    self._show_toast("Note exported successfully")
                else:
                    self._show_toast("Failed to export note")
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_export_json_clicked(self, btn, popover):
        popover.popdown()
        if not self.file_manager.active_file_path:
            return
            
        dialog = Gtk.FileChooserNative(
            title="Export Note to JSON",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Export",
            cancel_label="Cancel"
        )
        title = self.file_manager.get_display_title(self.file_manager.active_file_path)
        dialog.set_current_name(f"{title}.json")
        
        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON files (*.json)")
        filter_json.add_pattern("*.json")
        dialog.add_filter(filter_json)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                dest = dialog.get_file().get_path()
                if self.file_manager.export_note_to_json(self.file_manager.active_file_path, dest):
                    self._show_toast("Note exported successfully")
                else:
                    self._show_toast("Failed to export note")
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_import_markdown_clicked(self, btn, popover):
        popover.popdown()
        dialog = Gtk.FileChooserNative(
            title="Import Note from Markdown",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="Import",
            cancel_label="Cancel"
        )
        
        filter_md = Gtk.FileFilter()
        filter_md.set_name("Markdown files (*.md)")
        filter_md.add_pattern("*.md")
        dialog.add_filter(filter_md)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                src = dialog.get_file().get_path()
                target_nb = self.file_manager.active_notebook
                if self.file_manager.import_note_from_markdown(src, target_nb):
                    self._show_toast("Note imported successfully")
                    self.sidebar.populate()
                else:
                    self._show_toast("Failed to import note")
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_import_json_clicked(self, btn, popover):
        popover.popdown()
        dialog = Gtk.FileChooserNative(
            title="Import Note from JSON",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="Import",
            cancel_label="Cancel"
        )

        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON files (*.json)")
        filter_json.add_pattern("*.json")
        dialog.add_filter(filter_json)

        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                src = dialog.get_file().get_path()
                target_nb = self.file_manager.active_notebook
                if self.file_manager.import_note_from_json(src, target_nb):
                    self._show_toast("Note imported successfully")
                    self.sidebar.populate()
                else:
                    self._show_toast("Failed to import note")
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.show()

    def _on_export_pdf_clicked(self, btn, popover):
        popover.popdown()
        if not self.file_manager.active_file_path:
            return

        dialog = Gtk.FileChooserNative(
            title="Export Note to PDF",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Export",
            cancel_label="Cancel"
        )
        title = self.file_manager.get_display_title(self.file_manager.active_file_path)
        dialog.set_current_name(f"{title}.pdf")

        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF files (*.pdf)")
        filter_pdf.add_pattern("*.pdf")
        dialog.add_filter(filter_pdf)

        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                dest = dialog.get_file().get_path()
                if self.file_manager.export_note_to_pdf(self.file_manager.active_file_path, dest):
                    self._show_toast("Exported to PDF")
                else:
                    self._show_toast("Failed to export as PDF")
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.show()
