from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi
import datetime


gi.require_version('Gtk', '4.0')


class TrackItem(GObject.Object):
    __gtype_name__ = 'TrackItem'

    title = GObject.Property(type=str)
    track = GObject.Property(type=str)
    disc = GObject.Property(type=str)
    discsubtitle = GObject.Property(type=str)
    length = GObject.Property(type=int)
    path = GObject.Property(type=str)
    album = GObject.Property(type=str)
    artists = GObject.Property(type=str)
    albumartist = GObject.Property(type=str)

    thumb = GObject.Property(type=str)
    cover = GObject.Property(type=str)

    @GObject.Property(type=int)
    def discnumber(self) -> int:
        return int(self.disc.split('/')[0]) if self.disc else 0

    @GObject.Property(type=int)
    def tracknumber(self) -> int:
        return int(self.track.split('/')[0]) if self.track else 0

    @GObject.Property(type=str)
    def markup_title(self) -> str:
        return GLib.markup_escape_text(self.title)

    @GObject.Property(type=str)
    def duration(self) -> str:
        time = datetime.timedelta(seconds=self.length)
        return str(time) if self.length >= 3600 else str(time)[2:]

    def clone(self):
        return TrackItem(**dict(self))

    def __iter__(self):
        for property in self.list_properties():
            yield property.name, self.get_property(property.name)

    def __eq__(self, other) -> bool:
        return other and self.path == other.path


class AlbumItem(GObject.Object):
    __gtype_name__ = 'AlbumItem'

    title = GObject.Property(type=str)
    albumartist = GObject.Property(type=str)
    date = GObject.Property(type=str)
    length = GObject.Property(type=int)
    thumb = GObject.Property(type=str)
    cover = GObject.Property(type=str)

    artists = GObject.Property(type=GObject.TYPE_PYOBJECT)
    tracks = GObject.Property(type=GObject.TYPE_PYOBJECT)

    subtitle = GObject.Property(type=str)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tracks.sort(key=lambda t: (t.discnumber, t.tracknumber))
        self.num_tracks = len(self.tracks)

        self.subtitle = f'{self.duration} - {self.num_tracks} Tracks'
        if self.date:
            self.subtitle += f'\n{self.date}'

    @GObject.Property(type=str)
    def markup_title(self) -> str:
        return GLib.markup_escape_text(self.title)

    @GObject.Property(type=str)
    def duration(self) -> str:
        time = datetime.timedelta(seconds=self.length)
        return str(time) if self.length >= 3600 else str(time)[2:]

    def clone(self):
        return AlbumItem(**dict(self))

    def for_queue(self) -> dict:
        children = Gio.ListStore.new(QueueItem)
        children.splice(0, 0, [QueueItem(**dict(t)) for t in self.tracks])
        return {
            'title': self.title,
            'length': self.length,
            'thumb': self.thumb,
            'cover': self.cover,
            'children': children,
            'from_album': True,
        }

    def __eq__(self, other) -> bool:
        return (
            other
            and self.title == other.title
            and self.albumartist == other.albumartist
        )

    def __iter__(self):
        for property in self.list_properties():
            yield property.name, self.get_property(property.name)


class ArtistItem(GObject.Object):
    __gtype_name__ = 'ArtistItem'

    name = GObject.Property(type=str)
    raw_name = GObject.Property(type=str)
    sort = GObject.Property(type=str)
    albums = GObject.Property(type=str)

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
    """A TrackItem with additional properties for use in the playback queue.
    Inherits from TrackItem so that classes outside the queue that were
    expecting a TrackItem before the queue was turned into a TreeListModel still work.
    (List models need a single item type, but AlbumItems need to be added as root items,
    so they are converted to QueueItems. The QueueItems created from albums are filtered
     out from the actual queue, so they can't cause errors.)"""

    __gtype_name__ = 'RecordBoxQueueItem'

    subtitle = GObject.Property(type=str)
    position = GObject.Property(type=int, default=-1)
    is_current = GObject.Property(type=bool, default=False)
    from_album = GObject.Property(type=bool, default=False)
    children = GObject.Property(type=Gio.ListStore)

    def __init__(self, **kwargs):
        if 'children' in kwargs and type(kwargs['children']) == list:
            children = Gio.ListStore.new(QueueItem)
            children.splice(0, 0, [QueueItem(**t) for t in kwargs['children']])
            kwargs['children'] = children
        super().__init__(**kwargs)
        if self.from_album:
            self.subtitle = f'{self.duration} - {len(self.children)} Tracks'
        else:
            self.subtitle = self.duration

        if self.children:
            self.children.connect('items-changed', self._update)

    def clone(self, children=None):
        new = dict(self)
        if self.children or children:
            new['children'] = Gio.ListStore.new(QueueItem)
            new['children'].splice(
                0, 0, children or [c.clone() for c in self.children]
            )
            new['is_current'] = False
        return QueueItem(**new)

    def export(self):
        """Converts the QueueItem into a json-serializable dict."""
        out_dict = dict(self)
        if self.children:
            out_dict['children'] = [c.export() for c in self.children]
        else:
            del out_dict['children']
        out_dict['is_current'] = False
        return out_dict

    def _update(self, *_):
        self.length = sum(c.length for c in self.children)
        self.subtitle = f'{self.duration} - {len(self.children)} Tracks'

    def __eq__(self, other):
        if type(other) == TrackItem:
            return super().__eq__(other)
        else:
            return super().__eq__(other) and self.position == other.position
