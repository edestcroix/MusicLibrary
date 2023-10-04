from gi.repository import Gtk
import gi

gi.require_version('Gtk', '4.0')

from .musicrow import MusicRow


class RecordBoxList(Gtk.ListBox):
    __gtype_name__ = 'RecordBoxList'

    def __filter(self, row, user_data):
        return row.filter_key == user_data

    def filter_on_key(self, artist):
        self.set_filter_func(self.__filter, artist)

    def sort(self):
        self.set_sort_func(lambda row1, row2: row1.sort_key > row2.sort_key)
        self.invalidate_sort()

    def filter_all(self):
        self.set_filter_func(lambda _: True)

    def append(
        self, title, subtitle='', filter_key='', image_path='', date=''
    ):
        row = MusicRow(activatable=True, subtitle=subtitle)
        row.set_title(title, date)
        row.set_filter_key(filter_key) if filter_key else None
        row.set_sort_key(date) if date else None
        row.set_title_lines(1)
        if image_path:
            image = Gtk.Image()
            image.set_pixel_size(64)
            image.set_from_file(image_path)
            row.add_prefix(image)

        super().append(row)
