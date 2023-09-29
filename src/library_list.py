from gi.repository import Adw, Gtk, Gdk, GLib, Pango
import gi

gi.require_version('Gtk', '4.0')

from .musicrow import MusicRow


class MusicLibraryList(Gtk.ListBox):
    __gtype_name__ = 'MusicLibraryList'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def filter_on_key(self, artist):
        self.set_filter_func(self.__filter, artist)

    def filter_all(self):
        self.set_filter_func(lambda _: True)

    def __filter(self, row, user_data):
        return row.filter_key == user_data

    def append(self, title, subtitle='', filter_key='', image_path=''):
        row = MusicRow(activatable=True, subtitle=subtitle)
        row.set_title(title)
        row.set_filter_key(filter_key) if filter_key else None
        row.set_title_lines(1)
        if image_path:
            image = Gtk.Image()
            image.set_pixel_size(64)
            image.set_from_file(image_path)
            row.add_prefix(image)

        super().append(row)
