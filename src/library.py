from gi.repository import Adw, Gtk, GLib, GObject
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

    # either a MusicDB.Album or MusicDB.Artist.
    # This way both the album list and artist list can use the same row
    # Might create two classes later if necessary, but not needed right now.
    def set_data(self, data):
        self.data = data

    def set_title(self, title):
        super().set_title(f'{GLib.markup_escape_text(title)}')
        super().set_tooltip_text(super().get_title())
        self.raw_title = title


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
            subtitle=f'{album.date} - {album.num_tracks} tracks\n{album.length_str()}',
        )
        row.set_data(album)
        row.set_title(album.name)
        row.set_title_lines(1)

        row.set_filter_key(album.artists)
        if cover := album.cover:
            image = Gtk.Image.new_from_file(cover)
            image.set_pixel_size(64)
            row.add_prefix(image)
        super().append(row)

    def filter_on_key(self, key):
        self.set_filter_func(lambda r: key in r.filter_key)

    def filter_all(self):
        self.set_filter_func(lambda _: True)
