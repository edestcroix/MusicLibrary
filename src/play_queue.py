from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi
from .library import AlbumItem, TrackItem
from enum import Enum

Direction = Enum('Direction', 'NEXT PREV')

gi.require_version('Gtk', '4.0')


# TODO: Write unit tests for this class, especially for the delete_selected method
# to ensure the current index is updated correctly.
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

    select_all_button = Gtk.Template.Child()

    delete_selected = Gtk.Template.Child()

    jump_to_track = GObject.Signal()

    current_index = GObject.Property(type=int, default=-1)
    current_index_moved = False
    current_track = GObject.Property(type=TrackItem)

    jump_to_track = GObject.Signal()

    selected = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.model = Gio.ListStore.new(TrackItem)
        self.selection = Gtk.MultiSelection.new(self.model)

        self.track_list.set_model(self.selection)
        self.track_list.set_factory(self._create_factory())

        self.track_list.connect('activate', self._on_row_activated)
        self.selection.connect('selection-changed', self._check_selection)

        self.select_all_button.connect('clicked', lambda _: self.select_all())

    def _create_factory(self):
        factory = Gtk.SignalListItemFactory.new()
        factory.connect('setup', self._setup_row)
        factory.connect('bind', self._bind_row)
        return factory

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

    def clear(self):
        self.model.remove_all()
        self.selected = []
        self.current_index = -1

    def restart(self):
        self.current_index = 0

    def empty(self) -> bool:
        return len(self.model) == 0

    def get_next_track(self) -> TrackItem | None:
        if self.current_index_moved:
            self.current_index_moved = False
            return self.get_current_track()
        self._move_current(Direction.NEXT)
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
            self._move_current(Direction.NEXT)
        return 0 <= self.current_index < len(self.model)

    def previous(self) -> bool:
        self._move_current(Direction.PREV)
        if self.current_index_moved:
            self.current_index_moved = False
        return 0 <= self.current_index < len(self.model)

    @Gtk.Template.Callback()
    def _remove_selected(self, _):
        """Remove the selected tracks from the queue. Sorts the selected indicies
        and removes segments of sequential indicies with splice() instead of
        each track individually, since splice() is much more efficent."""
        if not self.selected:
            return

        self.selected.sort()
        old_index = self.current_index
        segment, removed = [], 0
        for i in self.selected:
            self.current_index -= i < old_index
            self.current_index_moved |= i == old_index
            if not segment or i == segment[-1] + 1:
                segment.append(i)
            else:
                self.model.splice(segment[0] - removed, len(segment), [])
                removed += len(segment)
                segment = [i]
        if segment:
            self.model.splice(segment[0] - removed, len(segment), [])
        self.selected = []
        self.current_track = self.get_current_track()
        # triggers an update of the current track highlight
        self.current_index = self.current_index

    def _move_current(self, direction: Direction):
        if direction == Direction.NEXT:
            self.current_index += 1
        elif direction == Direction.PREV:
            if self.current_index >= len(self.model):
                self.current_index = len(self.model) - 2
            else:
                self.current_index -= 1

    def _on_row_activated(self, _, index: int):
        self.current_index = index
        self.current_track = self.get_current_track()
        self.emit('jump-to-track')

    def _setup_row(self, _, item):
        row = QueueRow()
        item.set_child(row)
        item.bind_property(
            'position',
            row,
            'position',
            GObject.BindingFlags.DEFAULT,
        )
        self.bind_property(
            'current-index',
            row,
            'current-index',
            GObject.BindingFlags.DEFAULT,
        )

    def _bind_row(self, _, item):
        row = item.get_child()
        track = item.get_item()
        row.title = track.raw_title
        row.subtitle = track.length
        row.image_path = track.thumb

    def _check_selection(self, _, start, range_size):
        """Maintain a list of selected rows so we can delete them later.
        (Could just iterate over the list to find selected items on delete, but this
        way the delete button's sensitivity can be updated too."""
        for i in range(start, start + range_size):
            if self.selection.is_selected(i):
                if i not in self.selected:
                    self.selected.append(i)
            elif i in self.selected:
                self.selected.remove(i)
        self.delete_selected.set_sensitive(len(self.selected) > 0)


@Gtk.Template(
    resource_path='/com/github/edestcroix/RecordBox/lists/queue_row.ui'
)
class QueueRow(Adw.Bin):
    """Really basic wrapper around the UI file that could be used
    with a BuilderListItemFactory if we didn't need to bind the current-index"""

    __gtype_name__ = 'RecordBoxQueueRow'
    position = GObject.Property(type=int)
    current_index = GObject.Property(type=int)

    title = GObject.Property(type=str)
    subtitle = GObject.Property(type=str)
    image_path = GObject.Property(type=str)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.connect('notify::current-index', self._check_current)

    def _check_current(self, *_):
        if parent := self.get_parent():
            if self.current_index == self.position:
                parent.set_css_classes(
                    parent.get_css_classes() + ['current-track']
                )
            else:
                parent.set_css_classes(
                    list(set(parent.get_css_classes()) - {'current-track'})
                )
