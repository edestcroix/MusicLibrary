from gi.repository import Adw, Gtk, Gdk, GLib, Pango
import gi

gi.require_version('Gtk', '4.0')


class MusicRow(Adw.ActionRow):
    __gtype_name__ = 'MusicRow'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.filter_key = None
        self.raw_title = None
        self.sort_key = None

    def set_filter_key(self, key):
        self.filter_key = key

    def set_sort_key(self, key):
        self.sort_key = key

    def set_title(self, title, date=''):
        date = f'({date})' if date else ''
        super().set_title(f'{GLib.markup_escape_text(title)} {date}')
        self.raw_title = title
