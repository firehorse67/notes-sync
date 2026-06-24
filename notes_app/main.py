import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from .file_manager import FileManager
from .window import MainWindow

class NotesApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.michael.notesapp",
            flags=sys.argv[0] == ""
        )
        self.file_manager = None
        self.main_window = None

    def do_startup(self):
        Adw.Application.do_startup(self)

    def do_activate(self):
        # We instantiate FileManager here because we want it to start with the application
        if not self.file_manager:
            self.file_manager = FileManager()
            
        if not self.main_window:
            self.main_window = MainWindow(self, self.file_manager)
            
        self.main_window.present()

def main():
    app = NotesApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
