from gi.repository import Adw, GLib
import gi

gi.require_version('Adw', '1')


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
        super().set_tooltip_text(super().get_title())
        self.raw_title = title
