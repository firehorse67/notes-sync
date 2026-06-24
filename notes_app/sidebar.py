import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GObject, GLib, Gdk
import os
from datetime import datetime

class CreateNoteDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="New Note", transient_for=parent, modal=True)
        self.set_default_size(300, -1)
        
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Create", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        
        content_area = self.get_content_area()
        content_area.set_spacing(12)
        content_area.set_margin_start(16)
        content_area.set_margin_end(16)
        content_area.set_margin_top(16)
        content_area.set_margin_bottom(16)
        
        label = Gtk.Label(label="Enter a title for your note:")
        label.set_halign(Gtk.Align.START)
        content_area.append(label)
        
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("My New Note")
        self.entry.set_activates_default(True)
        content_area.append(self.entry)
        self.entry.grab_focus()

    def get_title(self):
        text = self.entry.get_text().strip()
        return text if text else "Untitled"


class CreateNotebookDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="New Notebook", transient_for=parent, modal=True)
        self.set_default_size(300, -1)
        
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Create", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        
        content_area = self.get_content_area()
        content_area.set_spacing(12)
        content_area.set_margin_start(16)
        content_area.set_margin_end(16)
        content_area.set_margin_top(16)
        content_area.set_margin_bottom(16)
        
        label = Gtk.Label(label="Enter a name for your notebook:")
        label.set_halign(Gtk.Align.START)
        content_area.append(label)
        
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Work")
        self.entry.set_activates_default(True)
        content_area.append(self.entry)
        self.entry.grab_focus()

    def get_name(self):
        return self.entry.get_text().strip()


class MoveNoteDialog(Gtk.Dialog):
    def __init__(self, parent, file_manager):
        super().__init__(title="Move Note", transient_for=parent, modal=True)
        self.set_default_size(300, -1)
        
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Move", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        
        content = self.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        
        label = Gtk.Label(label="Select destination notebook:")
        label.set_halign(Gtk.Align.START)
        content.append(label)
        
        notebooks = file_manager.get_notebooks()
        self.options = ["All Notes"] + notebooks
        
        self.string_list = Gtk.StringList.new(self.options)
        self.dropdown = Gtk.DropDown(model=self.string_list)
        
        active = file_manager.active_notebook
        if active in self.options:
            self.dropdown.set_selected(self.options.index(active))
        else:
            self.dropdown.set_selected(0)
            
        content.append(self.dropdown)

    def get_selected_notebook(self):
        idx = self.dropdown.get_selected()
        if idx == Gtk.INVALID_LIST_POSITION:
            return None
        name = self.options[idx]
        return None if name == "All Notes" else name


class NoteRow(Gtk.ListBoxRow):
    def __init__(self, title, file_path, mtime, tags, pinned=False):
        super().__init__()
        self.file_path = file_path
        self.title = title
        self.mtime = mtime
        self.tags = tags
        self.pinned = pinned

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.box.set_margin_start(16)
        self.box.set_margin_end(16)
        self.box.set_margin_top(10)
        self.box.set_margin_bottom(10)

        # Title row (with optional pin icon)
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.title_label = Gtk.Label()
        self.title_label.set_hexpand(True)
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.set_ellipsize(3)
        self.title_label.set_use_markup(True)
        self.update_title_label(title)
        title_row.append(self.title_label)

        self.pin_icon = Gtk.Image.new_from_icon_name("pin-symbolic")
        self.pin_icon.get_style_context().add_class("dim-label")
        self.pin_icon.set_visible(pinned)
        title_row.append(self.pin_icon)

        self.box.append(title_row)
        
        # Subtitle
        self.subtitle_label = Gtk.Label()
        self.subtitle_label.set_halign(Gtk.Align.START)
        self.subtitle_label.set_ellipsize(3)
        self.subtitle_label.get_style_context().add_class("dim-label")
        self.update_subtitle_label(mtime)
        self.box.append(self.subtitle_label)
        
        # Tags badges container
        self.tags_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.tags_box.set_margin_top(2)
        self.update_tags(tags)
        self.box.append(self.tags_box)
        
        self.set_child(self.box)

    def update_title_label(self, title):
        self.title = title
        self.title_label.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")

    def update_subtitle_label(self, mtime):
        self.mtime = mtime
        dt = datetime.fromtimestamp(mtime)
        today = datetime.now().date()
        date_val = dt.date()
        if date_val == today:
            time_str = dt.strftime("Today, %H:%M")
        elif (today - date_val).days == 1:
            time_str = dt.strftime("Yesterday, %H:%M")
        else:
            time_str = dt.strftime("%b %d, %Y")
        self.subtitle_label.set_text(time_str)

    def update_tags(self, tags):
        self.tags = tags
        for tag in tags:
            lbl = Gtk.Label(label=tag)
            lbl.get_style_context().add_class("tag-pill")
            self.tags_box.append(lbl)

    def update_pinned(self, pinned):
        self.pinned = pinned
        self.pin_icon.set_visible(pinned)


class TagManagerRow(Gtk.Box):
    def __init__(self, tag, parent_dialog, sidebar):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.tag = tag
        self.parent_dialog = parent_dialog
        self.sidebar = sidebar
        
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        
        lbl = Gtk.Label(label=tag)
        lbl.set_hexpand(True)
        lbl.set_halign(Gtk.Align.START)
        self.append(lbl)
        
        rename_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        rename_btn.set_tooltip_text("Rename Globally")
        rename_btn.connect("clicked", self._on_rename_clicked)
        self.append(rename_btn)
        
        delete_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        delete_btn.set_tooltip_text("Delete Globally")
        delete_btn.get_style_context().add_class("destructive-action")
        delete_btn.connect("clicked", self._on_delete_clicked)
        self.append(delete_btn)

    def _on_rename_clicked(self, btn):
        dialog = Gtk.Dialog(title="Rename Tag Globally", transient_for=self.parent_dialog, modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Rename", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        
        label = Gtk.Label(label=f"Rename tag '{self.tag}' globally to:")
        label.set_halign(Gtk.Align.START)
        content.append(label)
        
        entry = Gtk.Entry()
        entry.set_text(self.tag)
        entry.set_activates_default(True)
        content.append(entry)
        entry.grab_focus()
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                new_tag = entry.get_text().strip().lower()
                if new_tag and new_tag != self.tag:
                    self.sidebar.emit("rename-tag-global", self.tag, new_tag)
                    self.parent_dialog.response(Gtk.ResponseType.OK)
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_delete_clicked(self, btn):
        dialog = Adw.MessageDialog(
            transient_for=self.parent_dialog,
            heading="Delete Tag Globally?",
            body=f"Are you sure you want to permanently delete the tag '{self.tag}' from all notes? This cannot be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        
        def on_response(dialog, response_id):
            if response_id == "delete":
                self.sidebar.emit("delete-tag-global", self.tag)
                self.parent_dialog.response(Gtk.ResponseType.OK)
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()


class TagManagerDialog(Gtk.Dialog):
    def __init__(self, parent, file_manager, sidebar):
        super().__init__(title="Manage Tags", transient_for=parent, modal=True)
        self.set_default_size(320, 400)
        self.add_button("Close", Gtk.ResponseType.CLOSE)
        
        content = self.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        
        lbl = Gtk.Label(label="Manage tags globally across all notes:")
        lbl.set_halign(Gtk.Align.START)
        content.append(lbl)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        content.append(scrolled)
        
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(list_box)
        
        tags = file_manager.get_all_tags()
        for tag in tags:
            row = Gtk.ListBoxRow()
            row.set_child(TagManagerRow(tag, self, sidebar))
            list_box.append(row)


class SidebarView(Gtk.Box):
    __gsignals__ = {
        'note-selected': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'create-note': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'delete-note': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'rename-note': (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        'notebook-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),  # None for root
        'move-note': (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        'rename-tag-global': (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        'delete-tag-global': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'pin-note': (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
    }

    def __init__(self, file_manager):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.file_manager = file_manager
        self.active_path = None
        self.active_tag = None
        
        # --- Notebook Selector Bar ---
        self.notebook_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.notebook_bar.set_margin_start(8)
        self.notebook_bar.set_margin_end(8)
        self.notebook_bar.set_margin_top(8)
        self.notebook_bar.set_margin_bottom(4)
        
        # DropDown for notebooks
        self.notebook_list = Gtk.StringList.new(["All Notes"])
        self.notebook_dropdown = Gtk.DropDown(model=self.notebook_list)
        self.notebook_dropdown.set_hexpand(True)
        self.notebook_dropdown.connect("notify::selected", self._on_notebook_dropdown_changed)
        self.notebook_bar.append(self.notebook_dropdown)
        
        # New notebook button
        self.new_notebook_btn = Gtk.Button.new_from_icon_name("folder-new-symbolic")
        self.new_notebook_btn.set_tooltip_text("Create New Notebook")
        self.new_notebook_btn.connect("clicked", self._on_new_notebook_clicked)
        self.notebook_bar.append(self.new_notebook_btn)
        
        # Rename notebook button
        self.rename_notebook_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        self.rename_notebook_btn.set_tooltip_text("Rename Active Notebook")
        self.rename_notebook_btn.connect("clicked", self._on_rename_notebook_clicked)
        self.rename_notebook_btn.set_sensitive(False)
        self.notebook_bar.append(self.rename_notebook_btn)
        
        # Workspace/Notebook Actions Menu Button
        self.workspace_actions_btn = Gtk.MenuButton()
        self.workspace_actions_btn.set_icon_name("open-menu-symbolic")
        self.workspace_actions_btn.set_tooltip_text("Workspace / Notebook Actions")
        
        ws_popover = Gtk.Popover()
        ws_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ws_box.set_margin_start(6)
        ws_box.set_margin_end(6)
        ws_box.set_margin_top(6)
        ws_box.set_margin_bottom(6)
        
        # Notebook Actions
        self.exp_nb_zip_btn = Gtk.Button(label="Export Active Notebook (ZIP)...")
        self.exp_nb_zip_btn.set_has_frame(False)
        self.exp_nb_zip_btn.connect("clicked", self._on_export_notebook_zip_clicked, ws_popover)
        self.exp_nb_zip_btn.set_sensitive(False) # Default when All Notes is selected
        ws_box.append(self.exp_nb_zip_btn)
        
        self.exp_nb_json_btn = Gtk.Button(label="Export Active Notebook (JSON)...")
        self.exp_nb_json_btn.set_has_frame(False)
        self.exp_nb_json_btn.connect("clicked", self._on_export_notebook_json_clicked, ws_popover)
        self.exp_nb_json_btn.set_sensitive(False)
        ws_box.append(self.exp_nb_json_btn)
        
        ws_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        # Project Actions
        exp_proj_zip_btn = Gtk.Button(label="Export Entire Project (ZIP)...")
        exp_proj_zip_btn.set_has_frame(False)
        exp_proj_zip_btn.connect("clicked", self._on_export_project_zip_clicked, ws_popover)
        ws_box.append(exp_proj_zip_btn)
        
        exp_proj_json_btn = Gtk.Button(label="Export Entire Project (JSON)...")
        exp_proj_json_btn.set_has_frame(False)
        exp_proj_json_btn.connect("clicked", self._on_export_project_json_clicked, ws_popover)
        ws_box.append(exp_proj_json_btn)
        
        ws_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        # Import Actions
        imp_nb_zip_btn = Gtk.Button(label="Import Notebook from ZIP...")
        imp_nb_zip_btn.set_has_frame(False)
        imp_nb_zip_btn.connect("clicked", self._on_import_notebook_zip_clicked, ws_popover)
        ws_box.append(imp_nb_zip_btn)
        
        imp_proj_json_btn = Gtk.Button(label="Import Project from JSON...")
        imp_proj_json_btn.set_has_frame(False)
        imp_proj_json_btn.connect("clicked", self._on_import_project_json_clicked, ws_popover)
        ws_box.append(imp_proj_json_btn)
        
        ws_popover.set_child(ws_box)
        self.workspace_actions_btn.set_popover(ws_popover)
        self.notebook_bar.append(self.workspace_actions_btn)
        
        self.append(self.notebook_bar)
        
        # --- Search / Add Bar ---
        self.search_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.search_bar.set_margin_start(8)
        self.search_bar.set_margin_end(8)
        self.search_bar.set_margin_top(4)
        self.search_bar.set_margin_bottom(4)
        
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Search notes...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_bar.append(self.search_entry)
        
        self.add_button = Gtk.Button.new_from_icon_name("list-add-symbolic")
        self.add_button.set_tooltip_text("Create New Note")
        self.add_button.connect("clicked", self._on_add_clicked)
        self.search_bar.append(self.add_button)
        
        self.append(self.search_bar)
        
        # --- Tags Filter DropDown ---
        self.tag_filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.tag_filter_box.set_margin_start(8)
        self.tag_filter_box.set_margin_end(8)
        self.tag_filter_box.set_margin_top(4)
        self.tag_filter_box.set_margin_bottom(4)
        self.tag_filter_box.set_visible(False)
        
        lbl = Gtk.Label(label="Filter:")
        lbl.get_style_context().add_class("dim-label")
        self.tag_filter_box.append(lbl)
        
        self.tag_list = Gtk.StringList.new(["No Filter"])
        self.tag_dropdown = Gtk.DropDown(model=self.tag_list)
        self.tag_dropdown.set_hexpand(True)
        self.tag_dropdown.connect("notify::selected", self._on_tag_dropdown_changed)
        self.tag_filter_box.append(self.tag_dropdown)
        
        self.tag_manage_btn = Gtk.Button.new_from_icon_name("tag-symbolic")
        self.tag_manage_btn.set_tooltip_text("Manage Tags Globally")
        self.tag_manage_btn.connect("clicked", self._on_manage_tags_clicked)
        self.tag_filter_box.append(self.tag_manage_btn)
        
        self.append(self.tag_filter_box)
        
        # --- Notes ListBox ---
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.set_vexpand(True)
        self.append(self.scrolled_window)
        
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.connect("row-selected", self._on_row_selected)
        self.list_box.set_filter_func(self._filter_row)
        
        self.scrolled_window.set_child(self.list_box)
        
        # Right click actions
        gesture = Gtk.GestureClick.new()
        gesture.set_button(Gdk.BUTTON_SECONDARY)
        gesture.connect("released", self._on_right_click)
        self.list_box.add_controller(gesture)
        
        # File manager signals
        self.file_manager.connect("notebooks-changed", self._on_notebooks_changed_event)
        
        # Initial notebooks population
        self.update_notebooks_dropdown()

    def update_notebooks_dropdown(self):
        """Repopulate the notebook dropdown list."""
        notebooks = self.file_manager.get_notebooks()
        
        # Block dropdown listener to avoid double triggers
        self.notebook_dropdown.handler_block_by_func(self._on_notebook_dropdown_changed)
        
        current_selection = self.notebook_dropdown.get_selected()
        current_name = None
        if current_selection != Gtk.INVALID_LIST_POSITION:
            current_name = self.notebook_list.get_string(current_selection)
            
        # Re-build list model
        options = ["All Notes"] + notebooks
        self.notebook_list.splice(0, self.notebook_list.get_n_items(), options)
        
        # Select matching item or fallback to 0
        new_index = 0
        if current_name in options:
            new_index = options.index(current_name)
            
        self.notebook_dropdown.set_selected(new_index)
        self.notebook_dropdown.handler_unblock_by_func(self._on_notebook_dropdown_changed)

    def populate(self):
        """Populate list rows and tag badges."""
        selected_row = self.list_box.get_selected_row()
        selected_path = selected_row.file_path if selected_row else self.active_path
        
        # Clear note items
        while True:
            child = self.list_box.get_first_child()
            if not child:
                break
            self.list_box.remove(child)
            
        files = self.file_manager.get_files()
        
        row_to_select = None
        for file_info in files:
            title = self.file_manager.get_display_title(file_info['path'])
            row = NoteRow(title, file_info['path'], file_info['mtime'], file_info['tags'], file_info.get('pinned', False))
            self.list_box.append(row)
            
            if file_info['path'] == selected_path:
                row_to_select = row
                
        if row_to_select:
            self.list_box.select_row(row_to_select)
            
        # Repopulate tags filter dropdown
        self.populate_tags_filter()

    def update_note_row(self, path, title, mtime):
        """Update a single row's title and timestamp without rebuilding the whole list."""
        row = self.list_box.get_first_child()
        while row:
            if hasattr(row, 'file_path') and row.file_path == path:
                row.update_title_label(title)
                row.update_subtitle_label(mtime)
                return
            row = row.get_next_sibling()

    def populate_tags_filter(self):
        """Build tag filter dropdown options based on active tags."""
        tags = self.file_manager.get_all_tags()
        
        # Block dropdown selection listener
        self.tag_dropdown.handler_block_by_func(self._on_tag_dropdown_changed)
        
        # Re-build list model
        options = ["No Filter"] + tags
        self.tag_list.splice(0, self.tag_list.get_n_items(), options)
        
        # Keep selected tag
        if self.active_tag in options:
            self.tag_dropdown.set_selected(options.index(self.active_tag))
        else:
            self.active_tag = None
            self.tag_dropdown.set_selected(0)
            
        self.tag_dropdown.handler_unblock_by_func(self._on_tag_dropdown_changed)
        
        # Show/hide container
        self.tag_filter_box.set_visible(bool(tags))

    def _on_tag_dropdown_changed(self, dropdown, pspec):
        selected = dropdown.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION:
            return
            
        name = self.tag_list.get_string(selected)
        if name == "No Filter":
            self.active_tag = None
        else:
            self.active_tag = name
            
        self.list_box.invalidate_filter()

    def _on_manage_tags_clicked(self, button):
        dialog = TagManagerDialog(self.get_root(), self.file_manager, self)
        dialog.connect("response", lambda d, r: (self.populate(), d.destroy()))
        dialog.show()

    def _on_notebook_dropdown_changed(self, dropdown, pspec):
        """Switch notebooks when user selects from dropdown."""
        selected = dropdown.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION:
            return
            
        name = self.notebook_list.get_string(selected)
        if name == "All Notes":
            self.file_manager.set_active_notebook(None)
            self.rename_notebook_btn.set_sensitive(False)
            self.exp_nb_zip_btn.set_sensitive(False)
            self.exp_nb_json_btn.set_sensitive(False)
            self.emit("notebook-changed", "")
        else:
            self.file_manager.set_active_notebook(name)
            self.rename_notebook_btn.set_sensitive(True)
            self.exp_nb_zip_btn.set_sensitive(True)
            self.exp_nb_json_btn.set_sensitive(True)
            self.emit("notebook-changed", name)
            
        self.active_tag = None
        self.populate()

    def _on_rename_notebook_clicked(self, button):
        """Dialog to rename active notebook."""
        active = self.file_manager.active_notebook
        if not active:
            return
            
        dialog = Gtk.Dialog(title="Rename Notebook", transient_for=self.get_root(), modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Rename", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        
        label = Gtk.Label(label="Enter new notebook name:")
        label.set_halign(Gtk.Align.START)
        content.append(label)
        
        entry = Gtk.Entry()
        entry.set_text(active)
        entry.set_activates_default(True)
        content.append(entry)
        entry.grab_focus()
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                new_name = entry.get_text().strip()
                if new_name and new_name != active:
                    if self.file_manager.rename_notebook(active, new_name):
                        self.update_notebooks_dropdown()
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_new_notebook_clicked(self, button):
        """Dialog to create new notebook."""
        dialog = CreateNotebookDialog(self.get_root())
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                name = dialog.get_name()
                if name:
                    if self.file_manager.create_notebook(name):
                        # Force select the new notebook
                        self.update_notebooks_dropdown()
                        # Select it in DropDown
                        options = [self.notebook_list.get_string(i) for i in range(self.notebook_list.get_n_items())]
                        if name in options:
                            self.notebook_dropdown.set_selected(options.index(name))
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_notebooks_changed_event(self, file_manager):
        self.update_notebooks_dropdown()

    def _on_row_selected(self, list_box, row):
        if row:
            self.active_path = row.file_path
            self.emit("note-selected", row.file_path)
        else:
            self.active_path = None

    def _on_search_changed(self, entry):
        self.list_box.invalidate_filter()

    def _filter_row(self, row):
        # 1. Search text filter (title, filename, and full body)
        search_text = self.search_entry.get_text().strip().lower()
        if search_text:
            title_match = search_text in row.title.lower()
            filename_match = search_text in os.path.basename(row.file_path).lower()
            body_match = search_text in self.file_manager.get_body_text(row.file_path)
            if not (title_match or filename_match or body_match):
                return False

        # 2. Tag filter
        if self.active_tag:
            if self.active_tag not in row.tags:
                return False

        return True

    def _on_add_clicked(self, button):
        dialog = CreateNoteDialog(self.get_root())
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                title = dialog.get_title()
                self.emit("create-note", title)
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_right_click(self, gesture, n_press, x, y):
        row = self.list_box.get_row_at_y(int(y))
        if not row:
            return
            
        self.list_box.select_row(row)
        
        popover = Gtk.Popover()
        popover.set_parent(row)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(4)
        box.set_margin_end(4)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        
        pin_label = "Unpin" if row.pinned else "Pin"
        pin_btn = Gtk.Button(label=pin_label)
        pin_btn.set_has_frame(False)
        pin_btn.set_halign(Gtk.Align.FILL)
        pin_btn.connect("clicked", lambda b: self._on_context_pin(popover, row))
        box.append(pin_btn)

        rename_btn = Gtk.Button(label="Rename")
        rename_btn.set_has_frame(False)
        rename_btn.set_halign(Gtk.Align.FILL)
        rename_btn.connect("clicked", lambda b: self._on_context_rename(popover, row))
        box.append(rename_btn)
        
        move_btn = Gtk.Button(label="Move to Notebook")
        move_btn.set_has_frame(False)
        move_btn.set_halign(Gtk.Align.FILL)
        move_btn.connect("clicked", lambda b: self._on_context_move(popover, row))
        box.append(move_btn)
        
        delete_btn = Gtk.Button(label="Delete")
        delete_btn.set_has_frame(False)
        delete_btn.set_halign(Gtk.Align.FILL)
        delete_btn.get_style_context().add_class("destructive-action")
        delete_btn.connect("clicked", lambda b: self._on_context_delete(popover, row))
        box.append(delete_btn)
        
        popover.set_child(box)
        
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()

    def _on_context_pin(self, popover, row):
        popover.popdown()
        self.emit("pin-note", row.file_path, not row.pinned)

    def _on_context_rename(self, popover, row):
        popover.popdown()
        
        dialog = Gtk.Dialog(title="Rename Note", transient_for=self.get_root(), modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Rename", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        
        label = Gtk.Label(label="Enter new note title:")
        label.set_halign(Gtk.Align.START)
        content.append(label)
        
        entry = Gtk.Entry()
        entry.set_text(row.title)
        entry.set_activates_default(True)
        content.append(entry)
        entry.grab_focus()
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                new_title = entry.get_text().strip()
                if new_title and new_title != row.title:
                    self.emit("rename-note", row.file_path, new_title)
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_context_delete(self, popover, row):
        popover.popdown()
        
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(),
            heading="Delete Note?",
            body=f"Are you sure you want to permanently delete '{row.title}'? This action cannot be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        
        def on_response(dialog, response_id):
            if response_id == "delete":
                self.emit("delete-note", row.file_path)
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_context_move(self, popover, row):
        popover.popdown()
        dialog = MoveNoteDialog(self.get_root(), self.file_manager)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                target = dialog.get_selected_notebook()
                self.emit("move-note", row.file_path, target)
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    # --- Workspace & Notebook Import / Export Handlers ---
    def _on_export_notebook_zip_clicked(self, btn, popover):
        popover.popdown()
        nb = self.file_manager.active_notebook
        if not nb:
            return
            
        dialog = Gtk.FileChooserNative(
            title="Export Notebook to ZIP",
            transient_for=self.get_root(),
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Export",
            cancel_label="Cancel"
        )
        dialog.set_current_name(f"{nb}_export.zip")
        
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name("ZIP archives (*.zip)")
        filter_zip.add_pattern("*.zip")
        dialog.add_filter(filter_zip)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                dest = dialog.get_file().get_path()
                if self.file_manager.export_notebook_to_zip(nb, dest):
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Notebook exported to ZIP successfully")
                else:
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Failed to export notebook")
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_export_notebook_json_clicked(self, btn, popover):
        popover.popdown()
        nb = self.file_manager.active_notebook
        if not nb:
            return
            
        dialog = Gtk.FileChooserNative(
            title="Export Notebook to JSON",
            transient_for=self.get_root(),
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Export",
            cancel_label="Cancel"
        )
        dialog.set_current_name(f"{nb}_export.json")
        
        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON files (*.json)")
        filter_json.add_pattern("*.json")
        dialog.add_filter(filter_json)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                dest = dialog.get_file().get_path()
                if self.file_manager.export_notebook_to_json(nb, dest):
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Notebook exported to JSON successfully")
                else:
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Failed to export notebook")
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_export_project_zip_clicked(self, btn, popover):
        popover.popdown()
        dialog = Gtk.FileChooserNative(
            title="Export Entire Project to ZIP",
            transient_for=self.get_root(),
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Export",
            cancel_label="Cancel"
        )
        dialog.set_current_name("notes_project_backup.zip")
        
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name("ZIP archives (*.zip)")
        filter_zip.add_pattern("*.zip")
        dialog.add_filter(filter_zip)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                dest = dialog.get_file().get_path()
                if self.file_manager.export_project_to_zip(dest):
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Project exported to ZIP successfully")
                else:
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Failed to export project")
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_export_project_json_clicked(self, btn, popover):
        popover.popdown()
        dialog = Gtk.FileChooserNative(
            title="Export Entire Project to JSON",
            transient_for=self.get_root(),
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Export",
            cancel_label="Cancel"
        )
        dialog.set_current_name("notes_project_backup.json")
        
        filter_json = Gtk.FileFilter()
        filter_json.set_name("JSON files (*.json)")
        filter_json.add_pattern("*.json")
        dialog.add_filter(filter_json)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                dest = dialog.get_file().get_path()
                if self.file_manager.export_project_to_json(dest):
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Project exported to JSON successfully")
                else:
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Failed to export project")
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_import_notebook_zip_clicked(self, btn, popover):
        popover.popdown()
        dialog = Gtk.FileChooserNative(
            title="Import Notebook from ZIP",
            transient_for=self.get_root(),
            action=Gtk.FileChooserAction.OPEN,
            accept_label="Import",
            cancel_label="Cancel"
        )
        
        filter_zip = Gtk.FileFilter()
        filter_zip.set_name("ZIP archives (*.zip)")
        filter_zip.add_pattern("*.zip")
        dialog.add_filter(filter_zip)
        
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                src = dialog.get_file().get_path()
                if self.file_manager.import_notebook_from_zip(src):
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Notebook imported successfully")
                    self.update_notebooks_dropdown()
                    self.populate()
                else:
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Failed to import notebook")
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def _on_import_project_json_clicked(self, btn, popover):
        popover.popdown()
        dialog = Gtk.FileChooserNative(
            title="Import Project from JSON",
            transient_for=self.get_root(),
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
                if self.file_manager.import_project_from_json(src):
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Project imported successfully")
                    self.update_notebooks_dropdown()
                    self.populate()
                else:
                    win = self.get_root()
                    if win and hasattr(win, '_show_toast'):
                        win._show_toast("Failed to import project")
            dialog.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()



