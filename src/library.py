from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi
import datetime
from enum import Enum


class ArtistSort(Enum):
    NAME_ASC = 'name-ascending'
    NAME_DESC = 'name-descending'


class AlbumSort(Enum):
    NAME_ASC = 'name-ascending'
    NAME_DESC = 'name-descending'
    DATE_ASC = 'date-ascending'
    DATE_DESC = 'date-descending'


gi.require_version('Gtk', '4.0')


class TrackItem(GObject.Object):
    __gtype_name__ = 'TrackItem'

    track = GObject.Property(type=int)
    discnumber = GObject.Property(type=int)
    discsubtitle = GObject.Property(type=str)
    title = GObject.Property(type=str)
    raw_title = GObject.Property(type=str)
    length = GObject.Property(type=str)
    path = GObject.Property(type=str)
    album = GObject.Property(type=str)
    artists = GObject.Property(type=str)
    albumartist = GObject.Property(type=str)
    thumb = GObject.Property(type=str)
    cover = GObject.Property(type=str)

    def __init__(
        self,
        track=None,
        discnumber=None,
        discsubtitle=None,
        title=None,
        length=None,
        path=None,
        album=None,
        artists=None,
        albumartist=None,
        thumb=None,
        cover=None,
    ):
        super().__init__()
        track = int(track.split('/')[0]) if track else 0
        self.track = track
        discnumber = int(discnumber.split('/')[0]) if discnumber else 0
        self.discnumber = discnumber
        self.discsubtitle = discsubtitle
        self.title = GLib.markup_escape_text(title or '')
        self.raw_title = title
        self.length = self.length_str(int(length or 0))
        self.path = path
        self.album = album
        self.artists = artists
        self.albumartist = albumartist
        self.thumb = thumb
        self.cover = cover

    def clone(self):
        new = TrackItem()
        new.track = self.track
        new.discnumber = self.discnumber
        new.discsubtitle = self.discsubtitle
        new.title = self.title
        new.raw_title = self.raw_title
        new.length = self.length
        new.path = self.path
        new.album = self.album
        new.artists = self.artists
        new.albumartist = self.albumartist
        new.thumb = self.thumb
        new.cover = self.cover
        return new

    def length_str(self, length):
        time = datetime.timedelta(seconds=length)
        return str(time) if length >= 3600 else str(time)[2:]


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
        self.tracks.sort(key=lambda t: (t.discnumber, t.track))
        self.summary = f'{date} - {self.track_num} tracks\n{self.length_str()}'

    def length_str(self):
        time = datetime.timedelta(seconds=self.length)
        return str(time) if self.length >= 3600 else str(time)[2:]

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
        self.albums = f'{num_albums} album{"s" if num_albums > 1 else ""}'


class LibraryList(Gtk.ListView):
    """Base class for artist and album lists, since they're almost identical other than
    the album list needing a filter model."""

    __gtype_name__ = 'RecordBoxLibraryList'

    sort = GObject.Property(type=str)
    selected = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    focus_next = GObject.Signal()
    focus_prev = GObject.Signal()

    model: Gio.ListStore
    template: str

    def __init__(self):
        super().__init__()

        self._setup_model()
        self.set_factory(
            Gtk.BuilderListItemFactory.new_from_resource(
                Gtk.BuilderCScope(), self.template
            )
        )

        self.connect('notify::sort', lambda *_: self._update_sort())

        event_controller = Gtk.EventControllerKey.new()
        event_controller.connect('key-pressed', self._key_press)
        self.add_controller(event_controller)

    def append(self, item: GObject.Object):
        self.model.append(item)

    def populate(self, items: list[GObject.Object]):
        self.model.remove_all()
        self.model.splice(0, 0, items)
        self._update_sort()
        self.scroll_to(0, Gtk.ListScrollFlags.FOCUS)

    def unselect_all(self):
        # for some reason unselect_all() doesn't work on a SingleSelection
        self.selection_model.unselect_item(self.selection_model.get_selected())

    def remove_all(self):
        self.model.remove_all()

    def get_row_at_index(self, index: int) -> GObject.Object:
        return self.model[index]

    def select_index(self, index: int):
        self.selection_model.select_item(index, True)

    def _setup_model(self):
        self.selection_model = Gtk.SingleSelection.new(self.model)
        self.selection_model.set_can_unselect(True)
        self.selection_model.connect('selection_changed', self._item_selected)
        self.set_model(self.selection_model)

    def _item_selected(self, *_):
        if selected := self.selection_model.get_selected_item():
            self.emit('selected', selected)

    def _key_press(self, key_controller, keyval, keycode, state):
        if keycode == 114:
            self.emit('focus-next')
        elif keycode == 113:
            self.emit('focus-prev')

    def _update_sort(self):
        pass


class ArtistList(LibraryList):
    __gtype_name__ = 'RecordBoxArtistList'

    model = Gio.ListStore.new(ArtistItem)
    template = '/com/github/edestcroix/RecordBox/lists/artist_row.ui'

    def _update_sort(self):
        match ArtistSort(self.sort):
            case ArtistSort.NAME_ASC:
                self.model.sort(lambda a, b: a.sort < b.sort)
            case ArtistSort.NAME_DESC:
                self.model.sort(lambda a, b: a.sort > b.sort)


class AlbumList(LibraryList):
    __gtype_name__ = 'RecordBoxAlbumList'

    model = Gio.ListStore.new(AlbumItem)
    template = '/com/github/edestcroix/RecordBox/lists/album_row.ui'

    def get_row_at_index(self, index: int):
        return self.filter_model[index]

    def filter_all(self):
        self.filter_model.set_filter(None)

    def filter_on_artist(self, artist: str):
        self.filter_model.set_filter(
            Gtk.CustomFilter.new(lambda r: artist in r.artists)
        )
        self._item_selected()

    def find_album(self, album_name: str) -> AlbumItem | None:
        return next(
            (row for row in self.model if row.raw_name == album_name), None
        )

    def _setup_model(self):
        self.filter_model = Gtk.FilterListModel.new(self.model, None)
        self.selection_model = Gtk.SingleSelection.new(self.filter_model)
        self.selection_model.connect('selection_changed', self._item_selected)
        self.set_model(self.selection_model)

    def _update_sort(self):
        match AlbumSort(self.sort):
            case AlbumSort.NAME_ASC:
                self.model.sort(lambda a, b: a.name < b.name)
            case AlbumSort.NAME_DESC:
                self.model.sort(lambda a, b: a.name > b.name)
            case AlbumSort.DATE_ASC:
                self.model.sort(lambda a, b: a.date > b.date)
            case AlbumSort.DATE_DESC:
                self.model.sort(lambda a, b: a.date < b.date)
