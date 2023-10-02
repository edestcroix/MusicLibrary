
python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'musiclibrary.in',
  output: 'musiclibrary',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr--r--'
)

musiclibrary_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'musicdb.py',
  'album_view.py',
  'musicrow.py',
  'library_list.py',
  'player.py',
  'play_queue.py',
  'main_view.py',
]

install_data(musiclibrary_sources, install_dir: moduledir)
