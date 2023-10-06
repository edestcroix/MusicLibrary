from gi.repository import Gtk, GObject
import gi

gi.require_version('Gtk', '4.0')

from .musicrow import MusicRow


class RecordBoxArtistList(Gtk.ListBox):
    __gtype_name__ = 'RecordBoxArtistList'

    _sort_type = 0

    @GObject.Property(type=int)
    def sort(self):
        return self._sort_type

    @sort.setter
    def set_sort(self, value):
        self._sort_type = value
        self._update_sort()

    def _update_sort(self):
        if self._sort_type == 0:
            self.set_sort_func(lambda a, b: a.data.name > b.data.name)
        elif self._sort_type == 1:
            self.set_sort_func(lambda a, b: a.data.name < b.data.name)
        self.invalidate_sort()

    def append(self, artist):
        row = MusicRow(
            activatable=True, subtitle=f'{artist.num_albums} albums'
        )
        row.set_data(artist)
        row.set_title(artist.name)
        row.set_title_lines(1)
        super().append(row)


class RecordBoxAlbumList(Gtk.ListBox):
    __gtype_name__ = 'RecordBoxAlbumList'

    _sort_type = 0

    @GObject.Property(type=int)
    def sort(self):
        return self._sort_type

    @sort.setter
    def set_sort(self, value):
        self._sort_type = value
        self._update_sort()

    def _update_sort(self):
        if self._sort_type == 0:
            self.set_sort_func(lambda a, b: a.data.name > b.data.name)
        elif self._sort_type == 1:
            self.set_sort_func(lambda a, b: a.data.name < b.data.name)
        elif self._sort_type == 2:
            self.set_sort_func(
                lambda a, b: str(a.data.date) < str(b.data.date)
            )
        elif self._sort_type == 3:
            self.set_sort_func(
                lambda a, b: str(a.data.date) > str(b.data.date)
            )
        self.invalidate_sort()

    def append(self, album):
        row = MusicRow(
            activatable=True,
            subtitle=f'{album.length_str()} - {album.num_tracks} tracks',
        )
        row.set_data(album)
        row.set_title(album.name)
        row.set_title_lines(1)

        row.set_filter_key(album.artist)
        if cover := album.cover:
            image = Gtk.Image.new_from_file(cover)
            image.set_pixel_size(64)
            row.add_prefix(image)
        super().append(row)

    def filter_on_key(self, key):
        self.set_filter_func(lambda r: r.filter_key == key)

    def filter_all(self):
        self.set_filter_func(lambda _: True)
