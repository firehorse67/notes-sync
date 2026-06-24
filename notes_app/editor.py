import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Pango, GObject, Gdk, GLib, Gio, GdkPixbuf
import markdown
import os
import re
import shutil
from html.parser import HTMLParser

class HTMLToBufferParser(HTMLParser):
    def __init__(self, buffer, editor=None):
        super().__init__()
        self.buffer = buffer
        self.editor = editor
        self.active_tags = []
        self.list_type_stack = []   # 'ul' or 'ol' per nesting level
        self.ol_counters = []        # item counter per ol level
        self.in_pre = False
        self.current_line_is_empty = True
        self.in_attachment_link = None
        self.attachment_link_text = []

    def handle_starttag(self, tag, attrs):
        if tag == 'h1':
            self.active_tags.append('h1')
        elif tag == 'h2':
            self.active_tags.append('h2')
        elif tag == 'h3':
            self.active_tags.append('h3')
        elif tag == 'strong':
            self.active_tags.append('bold')
        elif tag == 'em':
            self.active_tags.append('italic')
        elif tag in ('ul', 'ol'):
            self.list_type_stack.append(tag)
            if tag == 'ol':
                self.ol_counters.append(0)
        elif tag == 'li':
            if self.list_type_stack and self.list_type_stack[-1] == 'ol':
                self.ol_counters[-1] += 1
                n = self.ol_counters[-1]
                self.active_tags.append('numbered')
                start_iter = self.buffer.get_end_iter()
                self.buffer.insert_with_tags_by_name(start_iter, f"{n}. ", "numbered")
            else:
                self.active_tags.append('bullet')
                start_iter = self.buffer.get_end_iter()
                self.buffer.insert_with_tags_by_name(start_iter, "• ", "bullet")
            self.current_line_is_empty = False
        elif tag == 'pre':
            self.in_pre = True
        elif tag == 'code':
            if self.in_pre:
                self.active_tags.append('code_block')
            else:
                self.active_tags.append('code_inline')
        elif tag == 'blockquote':
            self.active_tags.append('blockquote')
        elif tag == 'hr':
            self.active_tags.append('hr')
            start_iter = self.buffer.get_end_iter()
            self.buffer.insert_with_tags_by_name(start_iter, "────────────────────────────────────────", "hr")
            self.active_tags.remove('hr')
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
            self.current_line_is_empty = True
        elif tag == 'a':
            attrs_dict = dict(attrs)
            href = attrs_dict.get('href', '')
            if href.startswith('.attachments/') or '/.attachments/' in href:
                self.in_attachment_link = href
                self.attachment_link_text = []

    def handle_endtag(self, tag):
        if tag == 'h1':
            self.active_tags.remove('h1')
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
            self.current_line_is_empty = True
        elif tag == 'h2':
            self.active_tags.remove('h2')
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
            self.current_line_is_empty = True
        elif tag == 'h3':
            self.active_tags.remove('h3')
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
            self.current_line_is_empty = True
        elif tag == 'strong':
            self.active_tags.remove('bold')
        elif tag == 'em':
            self.active_tags.remove('italic')
        elif tag in ('ul', 'ol'):
            if self.list_type_stack:
                removed = self.list_type_stack.pop()
                if removed == 'ol' and self.ol_counters:
                    self.ol_counters.pop()
        elif tag == 'li':
            if 'numbered' in self.active_tags:
                self.active_tags.remove('numbered')
            elif 'bullet' in self.active_tags:
                self.active_tags.remove('bullet')
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
            self.current_line_is_empty = True
        elif tag == 'pre':
            self.in_pre = False
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
            self.current_line_is_empty = True
        elif tag == 'code':
            if 'code_block' in self.active_tags:
                self.active_tags.remove('code_block')
            elif 'code_inline' in self.active_tags:
                self.active_tags.remove('code_inline')
        elif tag == 'blockquote':
            if 'blockquote' in self.active_tags:
                self.active_tags.remove('blockquote')
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
            self.current_line_is_empty = True
        elif tag == 'p':
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
            self.current_line_is_empty = True
        elif tag == 'a' and self.in_attachment_link:
            display_name = "".join(self.attachment_link_text)
            start_iter = self.buffer.get_end_iter()
            anchor = self.buffer.create_child_anchor(start_iter)
            self.in_attachment_link = None
            self.attachment_link_text = []

    def handle_data(self, data):
        if not data:
            return
        if self.in_attachment_link is not None:
            self.attachment_link_text.append(data)
            return
        in_code = 'code_block' in self.active_tags or 'code_inline' in self.active_tags
        if data.isspace() and self.current_line_is_empty and not in_code:
            return
        start_iter = self.buffer.get_end_iter()
        names = [t for t in self.active_tags if t in (
            'h1', 'h2', 'h3', 'bold', 'italic',
            'bullet', 'numbered', 'code_block', 'code_inline', 'blockquote', 'hr'
        )]
        self.buffer.insert_with_tags_by_name(start_iter, data, *names)
        self.current_line_is_empty = False


class MarkdownEditor(Gtk.Box):
    __gsignals__ = {
        'content-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._is_loading = False
        self.active_file_path = None
        self.anchors_metadata = {}
        self._attachments = []

        # --- Formatting Toolbar ---
        self.toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.toolbar.get_style_context().add_class("formatting-toolbar")
        self.toolbar.set_margin_start(8)
        self.toolbar.set_margin_end(8)
        self.toolbar.set_margin_top(4)
        self.toolbar.set_margin_bottom(4)
        self.append(self.toolbar)

        btn_bold = Gtk.Button.new_from_icon_name("format-text-bold-symbolic")
        btn_bold.set_tooltip_text("Bold (Ctrl+B)")
        btn_bold.connect("clicked", lambda b: self.toggle_inline_tag("bold"))
        self.toolbar.append(btn_bold)

        btn_italic = Gtk.Button.new_from_icon_name("format-text-italic-symbolic")
        btn_italic.set_tooltip_text("Italic (Ctrl+I)")
        btn_italic.connect("clicked", lambda b: self.toggle_inline_tag("italic"))
        self.toolbar.append(btn_italic)

        btn_code_inline = Gtk.Button(label="`x`")
        btn_code_inline.set_tooltip_text("Inline Code")
        btn_code_inline.connect("clicked", lambda b: self.toggle_inline_tag("code_inline"))
        self.toolbar.append(btn_code_inline)

        self.toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        btn_h1 = Gtk.Button(label="H1")
        btn_h1.set_tooltip_text("Heading 1 (Ctrl+1)")
        btn_h1.connect("clicked", lambda b: self.set_line_format("h1"))
        self.toolbar.append(btn_h1)

        btn_h2 = Gtk.Button(label="H2")
        btn_h2.set_tooltip_text("Heading 2 (Ctrl+2)")
        btn_h2.connect("clicked", lambda b: self.set_line_format("h2"))
        self.toolbar.append(btn_h2)

        btn_h3 = Gtk.Button(label="H3")
        btn_h3.set_tooltip_text("Heading 3 (Ctrl+3)")
        btn_h3.connect("clicked", lambda b: self.set_line_format("h3"))
        self.toolbar.append(btn_h3)

        btn_bullet = Gtk.Button.new_from_icon_name("format-list-bullet-symbolic")
        btn_bullet.set_tooltip_text("Bullet List (Ctrl+8)")
        btn_bullet.connect("clicked", lambda b: self.set_line_format("bullet"))
        self.toolbar.append(btn_bullet)

        btn_numbered = Gtk.Button.new_from_icon_name("format-list-ordered-symbolic")
        btn_numbered.set_tooltip_text("Numbered List (Ctrl+9)")
        btn_numbered.connect("clicked", lambda b: self.set_line_format("numbered"))
        self.toolbar.append(btn_numbered)

        btn_code_block = Gtk.Button(label="```")
        btn_code_block.set_tooltip_text("Code Block (Ctrl+`)")
        btn_code_block.connect("clicked", lambda b: self.set_line_format("code_block"))
        self.toolbar.append(btn_code_block)

        btn_quote = Gtk.Button.new_from_icon_name("format-text-quote-symbolic")
        btn_quote.set_tooltip_text("Blockquote")
        btn_quote.connect("clicked", lambda b: self.set_line_format("blockquote"))
        self.toolbar.append(btn_quote)

        btn_normal = Gtk.Button(label="Normal")
        btn_normal.set_tooltip_text("Normal Text (Ctrl+0)")
        btn_normal.connect("clicked", lambda b: self.set_line_format("paragraph"))
        self.toolbar.append(btn_normal)

        self.toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        btn_attach = Gtk.Button.new_from_icon_name("mail-attachment-symbolic")
        btn_attach.set_tooltip_text("Insert Attachment")
        btn_attach.connect("clicked", self._on_insert_attachment_clicked)
        self.toolbar.append(btn_attach)

        # --- Scrolled Window ---
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.set_vexpand(True)
        self.append(self.scrolled_window)

        # --- TextBuffer and TextView ---
        self.buffer = Gtk.TextBuffer()
        self.view = Gtk.TextView.new_with_buffer(self.buffer)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.view.set_pixels_below_lines(8)
        self.view.set_pixels_inside_wrap(4)
        self.view.set_left_margin(32)
        self.view.set_right_margin(32)
        self.view.set_top_margin(24)
        self.view.set_bottom_margin(24)
        self.scrolled_window.set_child(self.view)

        # Buffer tags
        self.buffer.create_tag("h1", weight=Pango.Weight.BOLD, scale=1.6, pixels_above_lines=12, pixels_below_lines=6)
        self.buffer.create_tag("h2", weight=Pango.Weight.BOLD, scale=1.4, pixels_above_lines=10, pixels_below_lines=4)
        self.buffer.create_tag("h3", weight=Pango.Weight.BOLD, scale=1.2, pixels_above_lines=8, pixels_below_lines=2)
        self.buffer.create_tag("bullet", left_margin=24, pixels_above_lines=2, pixels_below_lines=2)
        self.buffer.create_tag("numbered", left_margin=24, pixels_above_lines=2, pixels_below_lines=2)
        self.buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.buffer.create_tag("italic", style=Pango.Style.ITALIC)
        self.buffer.create_tag("code_inline", family="monospace", background="#f1f3f5", foreground="#c0392b")
        self.buffer.create_tag("code_block", family="monospace", background="#f8f9fa", left_margin=16, right_margin=16, pixels_above_lines=1, pixels_below_lines=1)
        self.buffer.create_tag("blockquote", left_margin=32, pixels_above_lines=6, pixels_below_lines=6, style=Pango.Style.ITALIC, foreground="#4b5563")
        self.buffer.create_tag("hr", foreground="#9ca3af", pixels_above_lines=8, pixels_below_lines=8, scale=0.8)

        # CSS
        self.view.get_style_context().add_class("editor-view")
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .editor-view {
                background-color: #ffffff;
                color: #1f2937;
            }
            .editor-view text {
                font-family: sans-serif;
                font-size: 11pt;
            }
            .formatting-toolbar {
                background-color: rgba(255, 255, 255, 0.4);
                padding: 6px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.08);
            }
            box.attachment-pill {
                background: linear-gradient(135deg, #f9fafb, #f3f4f6);
                border: 1px solid rgba(0, 0, 0, 0.06);
                border-radius: 20px;
                padding: 6px 12px;
                color: #374151;
                margin: 4px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
            }
            box.attachment-pill:hover {
                background: linear-gradient(135deg, #f3f4f6, #e5e7eb);
                border-color: rgba(0, 0, 0, 0.12);
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.04);
            }
            .attachment-open-btn {
                color: #2563eb;
                font-weight: 500;
                font-size: 10pt;
                padding: 0 4px;
            }
            .attachment-open-btn:hover {
                color: #1d4ed8;
                text-decoration: underline;
            }
            .attachment-delete-btn {
                color: #9ca3af;
                min-width: 0;
                min-height: 0;
                padding: 0 2px;
                border-radius: 8px;
            }
            .attachment-delete-btn:hover {
                color: #ef4444;
                background-color: rgba(239, 68, 68, 0.1);
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.buffer.connect("changed", self._on_buffer_changed)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.view.add_controller(key_controller)

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self.view.add_controller(drop_target)

        # --- Attachment Pill Bar ---
        self.attachments_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.attachments_bar.set_visible(False)

        att_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        att_header.set_margin_start(12)
        att_header.set_margin_end(12)
        att_header.set_margin_top(8)
        att_header.set_margin_bottom(4)
        att_lbl = Gtk.Label(label="Attachments")
        att_lbl.get_style_context().add_class("dim-label")
        att_lbl.set_halign(Gtk.Align.START)
        att_header.append(att_lbl)
        self.attachments_bar.append(att_header)

        self.attachments_flow = Gtk.FlowBox()
        self.attachments_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.attachments_flow.set_margin_start(8)
        self.attachments_flow.set_margin_end(8)
        self.attachments_flow.set_margin_bottom(10)
        self.attachments_flow.set_max_children_per_line(4)
        self.attachments_flow.set_homogeneous(False)
        self.attachments_bar.append(self.attachments_flow)

        self.append(self.attachments_bar)

    def set_content(self, text, file_path=None):
        self.active_file_path = file_path
        self.anchors_metadata = {}
        self._attachments = []
        self._is_loading = True
        self.buffer.set_text("")

        while True:
            child = self.attachments_flow.get_first_child()
            if not child:
                break
            self.attachments_flow.remove(child)

        trimmed_text = text.strip()
        if trimmed_text:
            _ATT_RE = re.compile(r'(!?)\[([^\]]*)\]\((\.attachments/[^)]+)\)')

            def _collect_att(m):
                is_img = m.group(1) == '!'
                display = m.group(2)
                src = m.group(3)
                ext = os.path.splitext(src)[1].lower().lstrip('.')
                self._attachments.append({
                    'type': 'image' if is_img else 'file',
                    'src': src,
                    'alt': display,
                    'text': display,
                })
                self._add_attachment_pill(src, display, ext)
                return ''

            cleaned = _ATT_RE.sub(_collect_att, trimmed_text)
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()

            if cleaned:
                html = markdown.markdown(cleaned, extensions=['fenced_code'])
                parser = HTMLToBufferParser(self.buffer, self)
                parser.feed(html)

        self.attachments_bar.set_visible(bool(self._attachments))
        self.buffer.set_enable_undo(False)
        self.buffer.set_enable_undo(True)
        self._is_loading = False

    def get_content(self):
        """Serialize Gtk.TextBuffer content to clean Markdown."""
        line_count = self.buffer.get_line_count()
        markdown_lines = []  # list of (line_str, is_code_block, is_numbered, is_blockquote, is_hr)

        for line_idx in range(line_count):
            _, line_start = self.buffer.get_iter_at_line(line_idx)
            line_end = line_start.copy()
            if not line_end.ends_line():
                line_end.forward_to_line_end()

            line_text = self.buffer.get_slice(line_start, line_end, True)
            line_tags = {t.get_property("name") for t in line_start.get_tags()}

            is_h1 = "h1" in line_tags
            is_h2 = "h2" in line_tags
            is_h3 = "h3" in line_tags
            is_bullet = "bullet" in line_tags
            is_numbered = "numbered" in line_tags
            is_code_block = "code_block" in line_tags
            is_blockquote = "blockquote" in line_tags
            is_hr = "hr" in line_tags

            runs = []

            if "￼" in line_text:
                current_iter = line_start.copy()
                while current_iter.compare(line_end) < 0:
                    anchor = current_iter.get_child_anchor()
                    if anchor:
                        metadata = self.anchors_metadata.get(anchor)
                        if metadata:
                            if metadata['type'] == 'image':
                                text = f"![{metadata['alt']}]({metadata['src']})"
                            else:
                                text = f"[{metadata['text']}]({metadata['src']})"
                        else:
                            text = ""
                        runs.append((text, set(), True))
                        current_iter.forward_char()
                        continue

                    char_end = current_iter.copy()
                    char_end.forward_char()
                    char_text = self.buffer.get_slice(current_iter, char_end, True)
                    tag_names = {t.get_property("name") for t in current_iter.get_tags()}
                    inline_tags = tag_names & {"bold", "italic", "code_inline"}

                    if runs and not runs[-1][2] and runs[-1][1] == inline_tags:
                        runs[-1] = (runs[-1][0] + char_text, inline_tags, False)
                    else:
                        runs.append((char_text, inline_tags, False))
                    current_iter.forward_char()
            else:
                current_iter = line_start.copy()
                while current_iter.compare(line_end) < 0:
                    tag_names = {t.get_property("name") for t in current_iter.get_tags()}
                    inline_tags = tag_names & {"bold", "italic", "code_inline"}

                    next_toggle = current_iter.copy()
                    has_toggle = next_toggle.forward_to_tag_toggle(None)

                    if not has_toggle or next_toggle.compare(line_end) > 0:
                        run_end = line_end.copy()
                    else:
                        run_end = next_toggle

                    run_text = self.buffer.get_slice(current_iter, run_end, True)
                    if run_text:
                        runs.append((run_text, inline_tags, False))

                    current_iter = run_end.copy()

            line_content = ""
            for text, tags, is_anchor in runs:
                if is_bullet and text.startswith("• "):
                    text = text[2:]
                elif is_bullet and text.startswith("•"):
                    text = text[1:]

                if not text:
                    continue

                if is_anchor or is_code_block:
                    line_content += text
                elif "code_inline" in tags:
                    line_content += f"`{text}`"
                elif "bold" in tags and "italic" in tags:
                    line_content += f"***{text}***"
                elif "bold" in tags:
                    line_content += f"**{text}**"
                elif "italic" in tags:
                    line_content += f"*{text}*"
                else:
                    line_content += text

            if is_hr:
                line_markdown = "---"
            elif is_code_block:
                line_markdown = line_content.rstrip()
            elif is_h1:
                line_markdown = f"# {line_content.strip()}"
            elif is_h2:
                line_markdown = f"## {line_content.strip()}"
            elif is_h3:
                line_markdown = f"### {line_content.strip()}"
            elif is_bullet:
                line_markdown = f"- {line_content.strip()}"
            elif is_numbered:
                line_markdown = line_content.rstrip()  # "N. content" already in buffer text
            elif is_blockquote:
                line_markdown = f"> {line_content.strip()}"
            else:
                line_markdown = line_content.rstrip()

            markdown_lines.append((line_markdown, is_code_block, is_numbered, is_blockquote, is_hr))

        result = []
        in_list = False
        in_blockquote = False
        in_code_block = False

        for line, is_code, is_num, is_bq, is_hr_line in markdown_lines:
            trimmed = line.strip()

            if is_code:
                if not in_code_block:
                    if in_list or in_blockquote:
                        result.append("")
                        in_list = False
                        in_blockquote = False
                    elif result and result[-1] != "":
                        result.append("")
                    result.append("```")
                    in_code_block = True
                result.append(line)
                continue

            if in_code_block:
                result.append("```")
                result.append("")
                in_code_block = False

            if not trimmed:
                if result and result[-1] != "":
                    result.append("")
                continue

            if is_num or trimmed.startswith("- "):
                if not in_list and result and result[-1] != "":
                    result.append("")
                in_list = True
                in_blockquote = False
                result.append(line)
            elif is_bq:
                if not in_blockquote and result and result[-1] != "":
                    result.append("")
                in_blockquote = True
                in_list = False
                result.append(line)
            else:
                if in_list or in_blockquote:
                    result.append("")
                    in_list = False
                    in_blockquote = False
                elif result and result[-1] != "":
                    result.append("")
                result.append(line)

        if in_code_block:
            result.append("```")

        body = "\n".join(result).strip()
        if self._attachments:
            att_lines = "\n".join(
                f"![{a['alt']}]({a['src']})" if a['type'] == 'image' else f"[{a['text']}]({a['src']})"
                for a in self._attachments
            )
            body = body + "\n\n" + att_lines
        return body + "\n"

    def toggle_inline_tag(self, tag_name):
        bounds = self.buffer.get_selection_bounds()
        if not bounds:
            return
        start, end = bounds
        self.buffer.begin_user_action()
        try:
            if self._has_tag_in_range(start, end, tag_name):
                self.buffer.remove_tag_by_name(tag_name, start, end)
            else:
                self.buffer.apply_tag_by_name(tag_name, start, end)
        finally:
            self.buffer.end_user_action()

    def _has_tag_in_range(self, start, end, tag_name):
        curr = start.copy()
        while curr.compare(end) < 0:
            for tag in curr.get_tags():
                if tag.get_property("name") == tag_name:
                    return True
            curr.forward_char()
        return False

    def _count_preceding_numbered_items(self, from_iter):
        count = 0
        for i in range(from_iter.get_line() - 1, -1, -1):
            _, iter_at_line = self.buffer.get_iter_at_line(i)
            if "numbered" in {t.get_property("name") for t in iter_at_line.get_tags()}:
                count += 1
            else:
                break
        return count

    def set_line_format(self, format_type):
        self.buffer.begin_user_action()
        try:
            insert_mark = self.buffer.get_insert()
            iter_start = self.buffer.get_iter_at_mark(insert_mark)

            line_start = iter_start.copy()
            line_start.set_line_offset(0)

            line_end = line_start.copy()
            if not line_end.ends_line():
                line_end.forward_to_line_end()

            line_text = self.buffer.get_text(line_start, line_end, True)
            line_tag_names = [t.get_property("name") for t in line_start.get_tags()]
            is_currently_bullet = "bullet" in line_tag_names or line_text.startswith("• ")
            is_currently_numbered = "numbered" in line_tag_names

            if is_currently_bullet and format_type != "bullet":
                prefix_len = 2 if line_text.startswith("• ") else 1
                prefix_end = line_start.copy()
                prefix_end.forward_chars(prefix_len)
                self.buffer.delete(line_start, prefix_end)
                line_end = line_start.copy()
                if not line_end.ends_line():
                    line_end.forward_to_line_end()
            elif is_currently_numbered and format_type != "numbered":
                m = re.match(r'^(\d+\. )', line_text)
                if m:
                    prefix_end = line_start.copy()
                    prefix_end.forward_chars(len(m.group(1)))
                    self.buffer.delete(line_start, prefix_end)
                    line_end = line_start.copy()
                    if not line_end.ends_line():
                        line_end.forward_to_line_end()

            for tname in ["h1", "h2", "h3", "bullet", "numbered", "code_block", "blockquote"]:
                self.buffer.remove_tag_by_name(tname, line_start, line_end)

            if format_type in ["h1", "h2", "h3"]:
                self.buffer.apply_tag_by_name(format_type, line_start, line_end)
            elif format_type == "bullet":
                if not line_text.startswith("• "):
                    self.buffer.insert_with_tags_by_name(line_start, "• ", "bullet")
                    line_end = line_start.copy()
                    if not line_end.ends_line():
                        line_end.forward_to_line_end()
                self.buffer.apply_tag_by_name("bullet", line_start, line_end)
            elif format_type == "numbered":
                n = self._count_preceding_numbered_items(line_start) + 1
                if not re.match(r'^\d+\. ', line_text):
                    self.buffer.insert_with_tags_by_name(line_start, f"{n}. ", "numbered")
                    line_end = line_start.copy()
                    if not line_end.ends_line():
                        line_end.forward_to_line_end()
                self.buffer.apply_tag_by_name("numbered", line_start, line_end)
            elif format_type == "code_block":
                self.buffer.apply_tag_by_name("code_block", line_start, line_end)
            elif format_type == "blockquote":
                self.buffer.apply_tag_by_name("blockquote", line_start, line_end)
        finally:
            self.buffer.end_user_action()

    def _on_buffer_changed(self, buffer):
        if not self._is_loading:
            self.emit("content-changed")

    def set_editable(self, editable):
        self.view.set_editable(editable)
        self.view.set_sensitive(editable)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        is_ctrl = (state & Gdk.ModifierType.CONTROL_MASK) != 0

        if is_ctrl:
            if keyval in (Gdk.KEY_b, Gdk.KEY_B):
                self.toggle_inline_tag("bold")
                return True
            elif keyval in (Gdk.KEY_i, Gdk.KEY_I):
                self.toggle_inline_tag("italic")
                return True
            elif keyval == Gdk.KEY_1:
                self.set_line_format("h1")
                return True
            elif keyval == Gdk.KEY_2:
                self.set_line_format("h2")
                return True
            elif keyval == Gdk.KEY_3:
                self.set_line_format("h3")
                return True
            elif keyval == Gdk.KEY_0:
                self.set_line_format("paragraph")
                return True
            elif keyval == Gdk.KEY_8:
                self.set_line_format("bullet")
                return True
            elif keyval == Gdk.KEY_9:
                self.set_line_format("numbered")
                return True
            elif keyval == Gdk.KEY_grave:
                self.set_line_format("code_block")
                return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            insert_mark = self.buffer.get_insert()
            curr_iter = self.buffer.get_iter_at_mark(insert_mark)

            line_start = curr_iter.copy()
            line_start.set_line_offset(0)

            line_end = line_start.copy()
            if not line_end.ends_line():
                line_end.forward_to_line_end()

            line_text = self.buffer.get_text(line_start, line_end, True)
            line_tags = [t.get_property("name") for t in line_start.get_tags()]

            if "bullet" in line_tags or line_text.startswith("•"):
                cleaned_text = line_text.replace("•", "").strip()
                if not cleaned_text:
                    self.set_line_format("paragraph")
                    return True
                else:
                    self.buffer.begin_user_action()
                    try:
                        self.buffer.insert(curr_iter, "\n")
                        new_insert_mark = self.buffer.get_insert()
                        new_iter = self.buffer.get_iter_at_mark(new_insert_mark)
                        self.buffer.insert_with_tags_by_name(new_iter, "• ", "bullet")
                        new_line_start = new_iter.copy()
                        new_line_start.set_line_offset(0)
                        new_line_end = new_line_start.copy()
                        if not new_line_end.ends_line():
                            new_line_end.forward_to_line_end()
                        self.buffer.apply_tag_by_name("bullet", new_line_start, new_line_end)
                    finally:
                        self.buffer.end_user_action()
                    return True

            elif "numbered" in line_tags or re.match(r'^\d+\. ', line_text):
                cleaned_text = re.sub(r'^\d+\. ', '', line_text).strip()
                if not cleaned_text:
                    self.set_line_format("paragraph")
                    return True
                else:
                    m = re.match(r'^(\d+)\. ', line_text)
                    n = (int(m.group(1)) if m else 0) + 1
                    self.buffer.begin_user_action()
                    try:
                        self.buffer.insert(curr_iter, "\n")
                        new_insert_mark = self.buffer.get_insert()
                        new_iter = self.buffer.get_iter_at_mark(new_insert_mark)
                        self.buffer.insert_with_tags_by_name(new_iter, f"{n}. ", "numbered")
                        new_line_start = new_iter.copy()
                        new_line_start.set_line_offset(0)
                        new_line_end = new_line_start.copy()
                        if not new_line_end.ends_line():
                            new_line_end.forward_to_line_end()
                        self.buffer.apply_tag_by_name("numbered", new_line_start, new_line_end)
                    finally:
                        self.buffer.end_user_action()
                    return True

            elif any(t in line_tags for t in ["h1", "h2", "h3"]):
                self.buffer.begin_user_action()
                try:
                    self.buffer.insert(curr_iter, "\n")
                    new_insert_mark = self.buffer.get_insert()
                    new_iter = self.buffer.get_iter_at_mark(new_insert_mark)
                    new_line_start = new_iter.copy()
                    new_line_start.set_line_offset(0)
                    new_line_end = new_line_start.copy()
                    if not new_line_end.ends_line():
                        new_line_end.forward_to_line_end()
                    for tname in ["h1", "h2", "h3", "bullet", "numbered", "blockquote"]:
                        self.buffer.remove_tag_by_name(tname, new_line_start, new_line_end)
                finally:
                    self.buffer.end_user_action()
                return True

            elif "blockquote" in line_tags:
                cleaned_text = line_text.strip()
                if not cleaned_text:
                    self.set_line_format("paragraph")
                    return True
                else:
                    self.buffer.begin_user_action()
                    try:
                        self.buffer.insert(curr_iter, "\n")
                        new_insert_mark = self.buffer.get_insert()
                        new_iter = self.buffer.get_iter_at_mark(new_insert_mark)
                        new_line_start = new_iter.copy()
                        new_line_start.set_line_offset(0)
                        new_line_end = new_line_start.copy()
                        if not new_line_end.ends_line():
                            new_line_end.forward_to_line_end()
                        self.buffer.apply_tag_by_name("blockquote", new_line_start, new_line_end)
                    finally:
                        self.buffer.end_user_action()
                    return True

        elif keyval == Gdk.KEY_BackSpace:
            insert_mark = self.buffer.get_insert()
            curr_iter = self.buffer.get_iter_at_mark(insert_mark)

            line_start = curr_iter.copy()
            line_start.set_line_offset(0)

            line_tags = [t.get_property("name") for t in line_start.get_tags()]
            if "bullet" in line_tags and curr_iter.get_line_offset() <= 2:
                self.set_line_format("paragraph")
                return True
            elif "numbered" in line_tags and curr_iter.get_line_offset() <= 4:
                self.set_line_format("paragraph")
                return True
            elif "blockquote" in line_tags and curr_iter.get_line_offset() == 0:
                self.set_line_format("paragraph")
                return True

        return False

    def show_error_toast(self, message):
        root = self.get_root()
        if root and hasattr(root, "_show_toast"):
            root._show_toast(message)
        else:
            print(f"Toast: {message}")

    def _on_insert_attachment_clicked(self, button):
        root = self.get_root()
        dialog = Gtk.FileChooserNative(
            title="Select Attachment",
            transient_for=root if isinstance(root, Gtk.Window) else None,
            action=Gtk.FileChooserAction.OPEN
        )

        filter_all = Gtk.FileFilter()
        filter_all.set_name("Supported Attachments")
        for ext in ['pdf', 'doc', 'rtf', 'txt', 'md', 'json', 'zip', 'gzip', 'tar', 'png', 'jpg', 'jpeg', 'webp']:
            filter_all.add_pattern(f"*.{ext}")
            filter_all.add_pattern(f"*.{ext.upper()}")
        dialog.add_filter(filter_all)

        def on_response(d, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                file = d.get_file()
                if file:
                    path = file.get_path()
                    if path:
                        self._insert_attachment_file(path)
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show()

    def _on_drop(self, drop_target, value, x, y):
        if not isinstance(value, Gdk.FileList):
            return False
        files = value.get_files()
        if not files:
            return False
        for file in files:
            path = file.get_path()
            if path:
                self._insert_attachment_file(path)
        return True

    def _insert_attachment_file(self, filepath):
        if not self.active_file_path:
            self.show_error_toast("Please open or create a note first")
            return

        if not os.path.exists(filepath):
            self.show_error_toast("File does not exist")
            return

        filesize = os.path.getsize(filepath)
        if filesize > 10 * 1024 * 1024:
            self.show_error_toast(f"File exceeds 10MB limit ({filesize / 1024 / 1024:.1f} MB)")
            return

        filename = os.path.basename(filepath)
        name_parts = os.path.splitext(filename)
        ext = name_parts[1].lower().lstrip('.')
        allowed_exts = {'pdf', 'doc', 'rtf', 'txt', 'md', 'json', 'zip', 'gzip', 'tar', 'png', 'jpg', 'jpeg', 'webp'}
        if ext not in allowed_exts:
            self.show_error_toast(f"Unsupported file format: {ext}")
            return

        note_dir = os.path.dirname(self.active_file_path)
        attachments_dir = os.path.join(note_dir, ".attachments")
        os.makedirs(attachments_dir, exist_ok=True)

        target_filename = filename
        target_path = os.path.join(attachments_dir, target_filename)
        counter = 1
        while os.path.exists(target_path):
            target_filename = f"{name_parts[0]}_{counter}{name_parts[1]}"
            target_path = os.path.join(attachments_dir, target_filename)
            counter += 1

        try:
            shutil.copy2(filepath, target_path)
        except Exception as e:
            self.show_error_toast(f"Failed to copy file: {e}")
            return

        relative_src = f".attachments/{target_filename}"
        self._attachments.append({
            'type': 'image' if ext in ('png', 'jpg', 'jpeg', 'webp') else 'file',
            'src': relative_src,
            'alt': filename,
            'text': filename,
        })
        self._add_attachment_pill(relative_src, filename, ext)
        self.attachments_bar.set_visible(True)
        self.emit("content-changed")

    def _add_attachment_pill(self, relative_src, display_name, ext):
        note_dir = os.path.dirname(self.active_file_path) if self.active_file_path else ""
        full_path = os.path.join(note_dir, relative_src)

        pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        pill.get_style_context().add_class("attachment-pill")

        if ext in ('png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'):
            icon_name = "image-x-generic-symbolic"
        elif ext == 'pdf':
            icon_name = "document-pdf-symbolic"
        elif ext in ('zip', 'tar', 'tgz', 'gz', 'bz2', 'xz', 'rar', '7z'):
            icon_name = "package-x-generic-symbolic"
        elif ext in ('mp3', 'wav', 'ogg', 'm4a', 'flac'):
            icon_name = "audio-x-generic-symbolic"
        elif ext in ('mp4', 'mkv', 'avi', 'mov', 'webm'):
            icon_name = "video-x-generic-symbolic"
        elif ext in ('md', 'txt', 'rst', 'json', 'yaml', 'yml', 'xml', 'csv'):
            icon_name = "text-x-generic-symbolic"
        else:
            icon_name = "document-x-generic-symbolic"

        pill.append(Gtk.Image.new_from_icon_name(icon_name))

        open_btn = Gtk.Button(label=display_name)
        open_btn.set_has_frame(False)
        open_btn.get_style_context().add_class("attachment-open-btn")
        def on_open(b, path=full_path):
            try:
                file_uri = GLib.filename_to_uri(os.path.abspath(path), None)
                Gio.AppInfo.launch_default_for_uri(file_uri, None)
            except Exception as e:
                self.show_error_toast(f"No application available to open this file: {e}")
        open_btn.connect("clicked", on_open)
        pill.append(open_btn)

        if os.path.exists(full_path):
            sz = os.path.getsize(full_path)
            sz_str = f"({sz / 1024 / 1024:.2f} MB)" if sz >= 1024 * 1024 else f"({sz / 1024:.1f} KB)"
            lbl_size = Gtk.Label()
            lbl_size.set_markup(f"<span foreground='#6b7280' size='small'>{sz_str}</span>")
            pill.append(lbl_size)

        del_btn = Gtk.Button(label="×")
        del_btn.set_has_frame(False)
        del_btn.get_style_context().add_class("attachment-delete-btn")
        del_btn.set_tooltip_text("Remove attachment")
        def on_delete(b):
            self._remove_attachment(relative_src, full_path, pill)
        del_btn.connect("clicked", on_delete)
        pill.append(del_btn)

        # Image hover preview
        if ext in ('png', 'jpg', 'jpeg', 'webp') and os.path.exists(full_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(full_path, 256, 256, True)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                picture = Gtk.Picture.new_for_paintable(texture)
                picture.set_content_fit(Gtk.ContentFit.CONTAIN)
                picture.set_size_request(256, 256)

                preview_popover = Gtk.Popover()
                preview_popover.set_parent(pill)
                preview_popover.set_autohide(False)
                preview_popover.set_position(Gtk.PositionType.TOP)
                preview_popover.set_child(picture)

                motion = Gtk.EventControllerMotion()
                motion.connect("enter", lambda ctrl, x, y: preview_popover.popup())
                motion.connect("leave", lambda ctrl: preview_popover.popdown())
                pill.add_controller(motion)
            except Exception:
                pass  # skip preview if image can't be loaded

        self.attachments_flow.append(pill)

    def _remove_attachment(self, relative_src, full_path, pill_widget):
        self._attachments = [a for a in self._attachments if a['src'] != relative_src]

        parent = pill_widget.get_parent()
        if parent:
            self.attachments_flow.remove(parent)

        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except OSError as e:
                self.show_error_toast(f"Could not delete file: {e}")

        self.attachments_bar.set_visible(bool(self._attachments))
        self.emit("content-changed")
