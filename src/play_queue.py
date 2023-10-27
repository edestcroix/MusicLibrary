from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi
from .library import AlbumItem, TrackItem

gi.require_version('Gtk', '4.0')


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/play_queue.ui')
class PlayQueue(Adw.Bin):
    """A containter for the play queue, containing the entire view around the track list itself,
    so the functionality for determining when to enable or disable the track list's selection mode can be
    contained within this class instead of strewn across the MainView class.
    Most of it's functions and properties just pass through to it's child track list, since most
    property bindings are defined in the ui file.
    """

    __gtype_name__ = 'RecordBoxPlayQueue'
    track_list = Gtk.Template.Child()
    collapse = GObject.Signal()

    select_all = Gtk.Template.Child()

    queue_header = Gtk.Template.Child()
    delete_selected = Gtk.Template.Child()

    loop = GObject.property(type=bool, default=False)
    _selection_active = False

    jump_to_track = GObject.Signal()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind_property(
            'loop',
            self.track_list,
            'loop',
            GObject.BindingFlags.BIDIRECTIONAL,
        )
        self.bind_property(
            'selection-active',
            self.track_list,
            'selection-active',
            GObject.BindingFlags.BIDIRECTIONAL,
        )

        self.track_list.connect(
            'jump-to-track', lambda _: self.emit('jump-to-track')
        )

        self.delete_selected.set_sensitive(True)

        self.select_all.connect(
            'clicked', lambda _: self.track_list.select_all()
        )

    @GObject.Property(type=bool, default=False)
    def selection_active(self):
        return self._selection_active

    @selection_active.setter
    def set_selection_active(self, value: bool):
        self._selection_active = value
        if value:
            self.queue_header.set_css_classes(['header-accent'])
        else:
            self.queue_header.set_css_classes([])

    @Gtk.Template.Callback()
    def _on_queue_toggle(self, _):
        self.track_list.selection_active = False
        # tell the main view that the queue should be closed
        self.emit('collapse')

    @Gtk.Template.Callback()
    def _remove_selected(self, _):
        self.track_list.remove_selected()

    def get_current_track(self) -> TrackItem | None:
        return self.track_list.get_current_track()

    def get_next_track(self) -> TrackItem | None:
        return self.track_list.get_next_track()

    def playing_track(self) -> TrackItem | None:
        """Returns the currently playing track, regardless of if the queue is empty or not.
        (track_list.current_track doesn't update to None until get_next_track is called on
         an empty queue, while get_current_track returns None if the queue is empty)"""
        return self.track_list.current_track

    def restart(self):
        self.track_list.restart()

    def clear(self):
        self.track_list.clear()

    def empty(self):
        return self.track_list.empty()

    def add_album(self, album: AlbumItem):
        self.track_list.add_album(album)

    def add_track(self, track: TrackItem):
        self.track_list.add_track(track)

    def next(self):
        return self.track_list.next()

    def previous(self):
        return self.track_list.previous()


@Gtk.Template(
    resource_path='/com/github/edestcroix/RecordBox/lists/queue_row.ui'
)
class QueueRow(Adw.Bin):
    """Really basic wrapper around the UI file that could be used
    with a BuilderListItemFactory if we didn't need to bind the extra
    selection-active property to swap visiblility of the thumbnail and checkbutton."""

    __gtype_name__ = 'RecordBoxQueueRow'
    checkbutton = Gtk.Template.Child()

    selection_active = GObject.Property(type=bool, default=False)
    title = GObject.Property(type=str)
    subtitle = GObject.Property(type=str)
    image_path = GObject.Property(type=str)


class PlayQueueList(Gtk.ListView):
    __gtype_name__ = 'RecordBoxPlayQueueList'

    current_index = -1
    current_index_moved = False

    loop = GObject.property(type=bool, default=False)
    current_track = GObject.Property(type=TrackItem)

    jump_to_track = GObject.Signal()

    _selection_active = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = Gio.ListStore.new(TrackItem)
        self.selection = Gtk.MultiSelection.new(self.model)
        self.no_selection = Gtk.NoSelection.new(self.model)
        self.set_model(self.no_selection)

        self.factory = Gtk.SignalListItemFactory.new()
        self.factory.connect('setup', self._setup_row)
        self.factory.connect('bind', self._bind_row)
        self.set_factory(self.factory)

        self.connect('activate', self._on_row_activated)

    @GObject.Property(type=bool, default=False)
    def selection_active(self):
        return self._selection_active

    @selection_active.setter
    def set_selection_active(self, value: bool):
        self.unselect_all()
        self._selection_active = value
        if value:
            self.set_model(self.selection)
        else:
            self.set_model(self.no_selection)

    def add_album(self, album: AlbumItem):
        for track in album.tracks:
            # GListStores hate having the same GObject inserted twice.
            self.model.append(track.clone())

    def add_track(self, track: TrackItem):
        self.model.append(track.clone())

    def select_all(self):
        self.selection.select_all()

    def unselect_all(self):
        self.selection.unselect_all()

    def remove_selected(self):
        i = 0
        while i < len(self.model):
            if self.selection.is_selected(i):
                self.model.remove(i)
                self.current_index_moved = i == self.current_index
                if i < self.current_index:
                    self.current_index -= 1
                    self.current_track = self.get_current_track()
            else:
                i += 1

    def clear(self):
        self.model.remove_all()
        self.current_index = -1

    def restart(self):
        self.current_index = 0

    def empty(self) -> bool:
        return len(self.model) == 0

    def get_next_track(self) -> TrackItem | None:
        if self.current_index_moved:
            self.current_index_moved = False
            return self.get_current_track()
        self._move_current('next')
        return self.get_current_track()

    def get_current_track(self) -> TrackItem | None:
        if self.current_index == -1 and len(self.model) > 0:
            self.current_index = 0
        self.current_track = (
            self.model[self.current_index]
            if 0 <= self.current_index < len(self.model)
            else None
        )
        return self.current_track

    def next(self) -> bool:
        if self.current_index_moved:
            self.current_index_moved = False
        else:
            self._move_current('next', True)
        return 0 <= self.current_index < len(self.model)

    def previous(self) -> bool:
        self._move_current('prev')
        if self.current_index_moved:
            self.current_index_moved = False
        return 0 <= self.current_index < len(self.model)

    def _setup_row(self, _, item):
        row = QueueRow()
        item.set_child(row)
        item.bind_property(
            'selected',
            row.checkbutton,
            'active',
            GObject.BindingFlags.DEFAULT,
        )
        self.bind_property(
            'selection-active',
            row,
            'selection-active',
            GObject.BindingFlags.DEFAULT,
        )

    def _bind_row(self, _, item):
        row = item.get_child()
        track = item.get_item()
        row.title = track.raw_title
        row.subtitle = track.length
        row.image_path = track.thumb

    def _move_current(self, direction: str, allow_none=False):
        if direction == 'next':
            if self.current_index >= len(self.model):
                self.current_index = 0 if self.loop else len(self.model)
            else:
                self.current_index += 1
        elif direction == 'prev':
            if self.current_index <= 0:
                if allow_none:
                    self.current_index = -1
            elif self.current_index >= len(self.model):
                self.current_index = len(self.model) - 2
            else:
                self.current_index -= 1

    def _on_row_activated(self, _, index: int):
        if not self.selection_active:
            self.current_index = index
            self.current_track = self.get_current_track()
            self.emit('jump-to-track')
