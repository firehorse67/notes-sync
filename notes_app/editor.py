import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GtkSource', '5')
from gi.repository import Gtk, GtkSource, Pango, GObject, Gdk

class MarkdownEditor(Gtk.Box):
    __gsignals__ = {
        'content-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Flag to prevent triggering change signals during load
        self._is_loading = False
        
        # ScrolledWindow container for the GtkSourceView
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.set_vexpand(True)
        self.append(self.scrolled_window)
        
        # Create GtkSource.Buffer
        self.buffer = GtkSource.Buffer()
        
        # Enable Markdown language syntax highlighting
        lang_manager = GtkSource.LanguageManager.get_default()
        markdown_lang = lang_manager.get_language('markdown')
        if markdown_lang:
            self.buffer.set_language(markdown_lang)
            self.buffer.set_highlight_syntax(True)
        
        # Choose a theme/style scheme (default to Adwaita style if available)
        scheme_manager = GtkSource.StyleSchemeManager.get_default()
        scheme_ids = scheme_manager.get_scheme_ids()
        
        # Select best matching scheme
        # We can dynamically switch between light/dark, but let's first load 'adwaita' or default
        selected_scheme = None
        for preferred in ['adwaita', 'tango', 'classic']:
            if preferred in scheme_ids:
                selected_scheme = scheme_manager.get_scheme(preferred)
                break
        if selected_scheme:
            self.buffer.set_style_scheme(selected_scheme)
            
        # Create GtkSource.View
        self.view = GtkSource.View.new_with_buffer(self.buffer)
        self.view.set_show_line_numbers(True)
        self.view.set_highlight_current_line(True)
        self.view.set_auto_indent(True)
        self.view.set_insert_spaces_instead_of_tabs(True)
        self.view.set_tab_width(4)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.view.set_smart_backspace(True)
        
        # Premium layout: padding around editor content
        self.view.set_left_margin(32)
        self.view.set_right_margin(32)
        self.view.set_top_margin(24)
        self.view.set_bottom_margin(24)
        
        # Font styling via CSS
        self.view.get_style_context().add_class("editor-view")
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b".editor-view { font-family: monospace; font-size: 11pt; }")
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        # Add GtkSourceView to ScrolledWindow
        self.scrolled_window.set_child(self.view)
        
        # Connect change listener
        self.buffer.connect("changed", self._on_buffer_changed)

    def set_content(self, text):
        """Set the text content without triggering change notifications."""
        self._is_loading = True
        self.buffer.set_text(text)
        # Clear undo/redo history for the newly loaded file to avoid cross-file undos
        self.buffer.set_enable_undo(False)
        self.buffer.set_enable_undo(True)
        self._is_loading = False

    def get_content(self):
        """Retrieve the current text content of the buffer."""
        start_iter = self.buffer.get_start_iter()
        end_iter = self.buffer.get_end_iter()
        return self.buffer.get_text(start_iter, end_iter, True)

    def _on_buffer_changed(self, buffer):
        """Buffer changed callback."""
        if not self._is_loading:
            self.emit("content-changed")
            
    def set_editable(self, editable):
        """Enable or disable editing."""
        self.view.set_editable(editable)
        self.view.set_sensitive(editable)
