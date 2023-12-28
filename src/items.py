from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi
from enum import Enum
import datetime


class TrackProperties(Enum):
    TRACK_STR = 0
    RAW_TITLE = 1
    DISC_STR = 2
    DISCSUBTITLE = 3
    ALBUMARTIST = 4
    SECONDS = 5
    PATH = 6
    ALBUM = 7
    ARTISTS = 8
    THUMB = 9
    COVER = 10


class AlbumProperties(Enum):
    RAW_NAME = 0
    ALBUMARTIST = 1
    LENGTH = 2
    DATE = 3
    THUMB = 4
    COVER = 5


gi.require_version('Gtk', '4.0')


class TrackItem(GObject.Object):
    __gtype_name__ = 'TrackItem'

    track_str = GObject.Property(type=str)
    raw_title = GObject.Property(type=str)
    disc_str = GObject.Property(type=str)
    discsubtitle = GObject.Property(type=str)
    seconds = GObject.Property(type=int)
    path = GObject.Property(type=str)
    album = GObject.Property(type=str)
    artists = GObject.Property(type=str)
    albumartist = GObject.Property(type=str)
    thumb = GObject.Property(type=str)
    cover = GObject.Property(type=str)

    def __init__(self, *args):
        super().__init__()
        for i, arg in enumerate(args):
            self.set_property(TrackProperties(i).name.lower(), arg)

    def __iter__(self):
        for prop in TrackProperties:
            yield self.get_property(prop.name.lower())

    @GObject.Property(type=int)
    def discnumber(self) -> int:
        return int(self.disc_str.split('/')[0]) if self.disc_str else 0

    @GObject.Property(type=int)
    def track(self) -> int:
        return int(self.track_str.split('/')[0]) if self.track_str else 0

    @GObject.Property(type=int)
    def title(self) -> str:
        return GLib.markup_escape_text(self.raw_title)

    @GObject.Property(type=str)
    def length(self) -> str:
        time = datetime.timedelta(seconds=self.seconds)
        return str(time) if self.seconds >= 3600 else str(time)[2:]

    def clone(self):
        return TrackItem(*self)

    def __eq__(self, other) -> bool:
        return other and self.path == other.path


class AlbumItem(GObject.Object):
    __gtype_name__ = 'AlbumItem'

    raw_name = GObject.Property(type=str)
    albumartist = GObject.Property(type=str)
    length = GObject.Property(type=int)
    date = GObject.Property(type=str)
    thumb = GObject.Property(type=str)
    cover = GObject.Property(type=str)

    artists: list[str]
    tracks: list[TrackItem]

    compact = GObject.Property(type=bool, default=False)

    def __init__(self, *args, artists=None, tracks=None):
        super().__init__()
        for i, arg in enumerate(args):
            self.set_property(AlbumProperties(i).name.lower(), arg)

        self.date = self.date or ''
        self.artists = artists or []
        self.tracks = tracks or []
        self.tracks.sort(key=lambda t: (t.discnumber, t.track))
        self.num_tracks = len(self.tracks)

    def __iter__(self):
        for prop in AlbumProperties:
            yield self.get_property(prop.name.lower())

    @GObject.Property(type=str)
    def name(self) -> str:
        return GLib.markup_escape_text(self.raw_name)

    @GObject.Property(type=str)
    def summary(self) -> str:
        if self.date:
            return f'{self.length_str} - {self.num_tracks} track{"s" if self.num_tracks>1 else ""}\n{self.date}'
        else:
            return f'{self.length_str} - {self.num_tracks} track{"s" if self.num_tracks>1 else ""}'

    @GObject.Property(type=str)
    def length_str(self):
        time = datetime.timedelta(seconds=self.length)
        return str(time) if self.length >= 3600 else str(time)[2:]

    def clone(self):
        return AlbumItem(*self, artists=self.artists, tracks=self.tracks)

    def __eq__(self, other):
        return all(
            (
                self.raw_name == other.raw_name,
                self.date == other.date,
                self.artists == other.artists,
                self.tracks == other.tracks,
            )
        )


class ArtistItem(GObject.Object):
    __gtype_name__ = 'ArtistItem'

    name = GObject.Property(type=str)
    raw_name = GObject.Property(type=str)
    sort = GObject.Property(type=str)
    albums = GObject.Property(type=str)

    compact = GObject.Property(type=bool, default=False)

    def __init__(self, name, sort, num_albums):
        super().__init__()
        self.sort = (
            'AAAAAAAAAAAAAAAAAAAA'
            if name == '[Various Artists]'
            else (sort or name)
        )
        self.name = GLib.markup_escape_text(name)
        self.raw_name = name
        self.albums = f'{num_albums} album{"s" if num_albums > 1 else ""}'

    # NOTE: Artists currently do not have a unique identifier. (They do in the database,
    # but any two given ArtistItems could have identical properties.) Might need to be
    # addressed in the future.
    def __eq__(self, other):
        return self.name == other.name


class QueueItem(TrackItem):
    """A TrackItem with additional properties for use in the playback queue. Basically,
    since a list model can only have one object type. Since before rewriting the play queue
    to use a TreeListModel, it was using TrackItems, and the rest of the code still expects that.
    Rather than rewrite everything, the QueueItem just inherits from TrackItem and adds the
    additional properties that the queue needs (Also the play_queue will never return a QueueItem
    that wasn't made from a TrackItem)."""

    __gtype_name__ = 'RecordBoxQueueItem'

    subtitle = GObject.Property(type=str)
    image_path = GObject.Property(type=str)

    position = GObject.Property(type=int, default=-1)

    is_current = GObject.Property(type=bool, default=False)
    from_album = GObject.Property(type=bool, default=False)
    children = GObject.Property(type=Gio.ListStore)

    def __init__(self, item: TrackItem | AlbumItem):
        if type(item) is AlbumItem:
            super().__init__(
                '',
                item.raw_name,
                '',
                '',
                '',
                item.length,
                '',
                '',
                '',
                item.thumb,
                item.cover,
            )
            self.subtitle = f'{len(item.tracks)} Tracks ({self.length})'
            self.children = Gio.ListStore.new(QueueItem)
            self.children.splice(
                0, len(self.children), [QueueItem(t) for t in item.tracks]
            )
            self.from_album = True
        else:
            super().__init__(*item)
            self.subtitle = item.length

        self.image_path = item.thumb

    def __eq__(self, other):
        if type(other) == TrackItem:
            return super().__eq__(other)
        else:
            return super().__eq__(other) and self.position == other.position

    def clone(self):
        new = QueueItem(super().clone())
        new.subtitle = self.subtitle
        if self.children:
            new.children = Gio.ListStore.new(QueueItem)
            new.children.splice(0, 0, [c.clone() for c in self.children])
        new.from_album = self.from_album
        # is_current is not cloned because it should not be a persistent property
        return new
