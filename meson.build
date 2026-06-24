project('notes-app',
  version: '0.1.0',
  meson_version: '>= 0.56.0',
  default_options: [ 'warning_level=1' ],
)

python = import('python')
py3 = python.find_installation('python3')

# Verify required system dependencies are present via pkg-config
dependency('gtk4', version: '>= 4.0.0')
dependency('libadwaita-1', version: '>= 1.0.0')
dependency('gtksourceview-5', version: '>= 5.0.0')

# Source directory install config
install_subdir(
  'notes_app',
  install_dir: py3.get_install_dir()
)

# Install launcher script
configure_file(
  input: 'run.py',
  output: 'notes-app',
  copy: true,
  install: true,
  install_dir: get_option('bindir')
)
