from gi.repository import Adw, Gtk, Gdk, GLib, Pango
import gi

gi.require_version('Gtk', '4.0')


class MusicRow(Adw.ActionRow):
    __gtype_name__ = 'MusicRow'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.filter_key = None
        self.raw_title = None

    def set_filter_key(self, key):
        self.filter_key = key

    def set_title(self, title):
        super().set_title(GLib.markup_escape_text(title))
        self.raw_title = title
