from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi

gi.require_version('Gtk', '4.0')


class TrackItem(GObject.Object):
    __gtype_name__ = 'TrackItem'

    track = GObject.Property(type=int)
    discnumber = GObject.Property(type=int)
    title = GObject.Property(type=str)
    length = GObject.Property(type=str)
    path = GObject.Property(type=str)
    album = GObject.Property(type=str)
    artists = GObject.Property(type=str)
    albumartist = GObject.Property(type=str)

    def __init__(
        self,
        track,
        discnumber,
        title,
        length,
        path,
        album,
        artists,
        albumartist,
    ):
        super().__init__()
        track = int(track.split('/')[0]) if track else 0
        self.track = track
        discnumber = int(discnumber.split('/')[0]) if discnumber else 0
        self.discnumber = discnumber
        self.title = GLib.markup_escape_text(title)
        self.length = self.length_str(int(length))
        self.path = path
        self.album = album
        self.artists = artists
        self.albumartist = albumartist

    def length_str(self, length):
        if length // 60 > 60:
            return f'{length // 3600}:{length % 3600 // 60}:{length % 60:02}'
        return f'{length // 60}:{length % 60:02}'


class AlbumItem(GObject.Object):
    __gtype_name__ = 'AlbumItem'

    name = GObject.Property(type=str)
    raw_name = GObject.Property(type=str)
    length = GObject.Property(type=int)
    date = GObject.Property(type=str)
    thumb = GObject.Property(type=str)
    cover = GObject.Property(type=str)
    num_tracks = GObject.Property(type=int)
    summary = GObject.Property(type=str)
    artists: list[str]
    tracks: list[TrackItem]

    def __init__(self, name, length, date, thumb, cover, artists, tracks):
        super().__init__()
        self.name = GLib.markup_escape_text(name)
        self.raw_name = name
        self.length = length
        self.date = date
        self.thumb = thumb
        self.cover = cover
        self.artists = artists
        self.track_num = len(tracks)
        self.tracks = tracks
        self.tracks.sort(key=lambda t: t.track + t.discnumber * 100)
        self.summary = f'{date} - {self.track_num} tracks\n{self.length_str()}'

    def length_str(self):
        if self.length // 60 > 60:
            return f'{self.length // 3600}:{self.length % 3600 // 60}:{self.length % 60:02}'
        return f'{self.length // 60}:{self.length % 60:02}'

    def copy(self):
        return AlbumItem(
            self.name,
            self.length,
            self.date,
            self.thumb,
            self.cover,
            self.artists,
            self.tracks,
        )


class ArtistItem(GObject.Object):
    __gtype_name__ = 'ArtistItem'

    name = GObject.Property(type=str)
    raw_name = GObject.Property(type=str)
    sort = GObject.Property(type=str)
    albums = GObject.Property(type=str)

    def __init__(self, name, sort, num_albums):
        super().__init__()
        self.name = GLib.markup_escape_text(name)
        self.raw_name = name
        self.sort = sort or name
        self.albums = f'{num_albums} albums'


class ArtistList(Gtk.ListView):
    __gtype_name__ = 'RecordBoxArtistList'

    _sort_type = 0

    artist_selected = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = Gio.ListStore.new(ArtistItem)
        self.selection_model = Gtk.SingleSelection.new(self.model)
        self.selection_model.set_can_unselect(True)
        self.selection_model.set_autoselect(False)
        self.selection_model.connect(
            'selection_changed', self._artist_selected
        )
        self.set_model(self.selection_model)
        factory = Gtk.BuilderListItemFactory.new_from_resource(
            Gtk.BuilderCScope(),
            '/com/github/edestcroix/RecordBox/lists/artist_row.ui',
        )
        self.set_factory(factory)

    @GObject.Property(type=int)
    def sort(self):
        return self._sort_type

    @sort.setter
    def set_sort(self, value: int):
        self._sort_type = value
        self._update_sort()

    def append(self, artist: ArtistItem):
        self.model.append(artist)

    def populate(self, artist_list: list[ArtistItem]):
        self.model.remove_all()
        for artist in artist_list:
            self.append(artist)
        self._update_sort()

    def unselect_all(self):
        self.selection_model.unselect_item(self.selection_model.get_selected())

    def remove_all(self):
        self.model.remove_all()

    def _update_sort(self):
        if self._sort_type == 0:
            self.model.sort(lambda a, b: a.sort > b.sort)
        elif self._sort_type == 1:
            self.model.sort(lambda a, b: a.sort < b.sort)

    def _artist_selected(self, selection_model, position, _):
        if selected := selection_model.get_selected_item():
            self.emit('artist-selected', selected)


class AlbumList(Gtk.ListView):
    __gtype_name__ = 'RecordBoxAlbumList'

    _sort_type = 0

    album_selected = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = Gio.ListStore.new(AlbumItem)

        self.filter_model = Gtk.FilterListModel.new(self.model, None)

        self.selection_model = Gtk.SingleSelection.new(self.filter_model)
        self.selection_model.connect('selection_changed', self._album_selected)
        self.selection_model.set_can_unselect(True)
        self.selection_model.set_autoselect(False)
        self.set_model(self.selection_model)
        factory = Gtk.BuilderListItemFactory.new_from_resource(
            Gtk.BuilderCScope(),
            '/com/github/edestcroix/RecordBox/lists/album_row.ui',
        )
        self.set_factory(factory)

    @GObject.Property(type=int)
    def sort(self):
        return self._sort_type

    @sort.setter
    def set_sort(self, value: int):
        self._sort_type = value
        self._update_sort()

    def append(self, album: AlbumItem):
        self.model.append(album)

    def populate(self, album_list: list[AlbumItem]):
        self.model.remove_all()
        for album in album_list:
            self.append(album)
        self._update_sort()

    def filter_on_artist(self, artist: str):
        self.filter_model.set_filter(
            Gtk.CustomFilter.new(lambda r: artist in r.artists)
        )

    def unselect_all(self):
        self.selection_model.unselect_item(self.selection_model.get_selected())

    def filter_all(self):
        self.unselect_all()
        self.filter_model.set_filter(None)

    def remove_all(self):
        self.model.remove_all()

    def _update_sort(self):
        if self._sort_type == 0:
            self.model.sort(lambda a, b: a.sort > b.sort)
        elif self._sort_type == 1:
            self.model.sort(lambda a, b: a.sort < b.sort)
        elif self._sort_type == 2:
            self.model.sort(lambda a, b: a.date < b.date)
        elif self._sort_type == 3:
            self.model.sort(lambda a, b: a.date > b.date)

    def _album_selected(self, selection_model, position, _):
        if selected := selection_model.get_selected_item():
            self.emit('album-selected', selected)
