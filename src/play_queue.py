from collections import deque
from collections.abc import Generator
from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi
from .items import AlbumItem, TrackItem
from enum import Enum

Direction = Enum('Direction', 'NEXT PREV')

gi.require_version('Gtk', '4.0')


# TODO: Write unit tests for this class, especially for the delete_selected method
# to ensure the current index is updated correctly.
@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/play_queue.ui')
class PlayQueue(Adw.Bin):
    __gtype_name__ = 'RecordBoxPlayQueue'
    """A containter for the play queue, containing the entire view around the track list itself,
    and the operations to manage the queue and maintain current track state."""

    track_list = Gtk.Template.Child()
    select_all_button = Gtk.Template.Child()
    delete_selected = Gtk.Template.Child()

    current_index = GObject.Property(type=int, default=-1)
    current_track = GObject.Property(type=TrackItem)

    jump_to_track = GObject.Signal()
    collapse = GObject.Signal()

    selected = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.model = Gio.ListStore.new(TrackItem)
        self.backups = deque(maxlen=10)

        self.selection = Gtk.MultiSelection.new(self.model)

        self.track_list.set_model(self.selection)
        self.track_list.set_factory(self._create_factory())

        self.selection.connect('selection-changed', self._check_selection)

    def append(self, tracks: list[TrackItem]):
        self._backup_queue()
        self.model.splice(len(self.model), 0, [t.clone() for t in tracks])

    def overwrite(self, tracks: list[TrackItem]):
        self._backup_queue(save_index=True)
        self.model.splice(0, len(self.model), [t.clone() for t in tracks])
        self.selected = []
        self.select_all_button.set_active(False)
        self.current_index = 0

    def add_after_current(self, track: TrackItem):
        self._backup_queue()
        self.model.splice(self.current_index + 1, 0, [track.clone()])

    def set_index(self, index: int):
        self.current_index = index

    # TODO: Redo?
    def undo(self, *_):
        self._restore_queue()

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

    def is_empty(self) -> bool:
        return len(self.model) == 0

    def index_synced(self) -> bool:
        """Checks if the current_track and the track at current_index are the same.
        When they are not, it means the current track was changed outside of normal
        queue advancement like get_next_track(), jumping to a track, or next() and previous().
        (E.g the current track was deleted from the queue or a restored backup changed current_index)"""
        return (
            self.model and self.current_track == self.model[self.current_index]
        )

    def get_next_track(self) -> TrackItem | None:
        # Only advance if the index is synced, because otherwise
        # the next track is already at the current index
        if self.index_synced():
            self._move_current(Direction.NEXT)
        return self.get_current_track()

    def get_current_track(self) -> TrackItem | None:
        """Retrieves the current track from the queue, and sets self.current_track
        to the value retrieved. Uses self.current_index to determine the track to
        get, meaning that if the two values are unsynced, they will resync after the next call
        to this method."""

        if self.current_index == -1 and len(self.model) > 0:
            self.current_index = 0
        if 0 <= self.current_index < len(self.model):
            self.current_track = self.model[self.current_index]
        else:
            self.current_track = None
        return self.current_track

    def next(self) -> bool:
        # don't advance if the index is unsynced, same as get_next_track()
        if self.index_synced():
            self._move_current(Direction.NEXT)
        return 0 <= self.current_index < len(self.model)

    def previous(self) -> bool:
        self._move_current(Direction.PREV)
        return 0 <= self.current_index < len(self.model)

    @Gtk.Template.Callback()
    def toggle_selection(self, button):
        if button.get_active():
            self.select_all()
        else:
            self.unselect_all()

    def remove_backups(self):
        self.backups.clear()

    def _create_factory(self):
        factory = Gtk.SignalListItemFactory.new()
        factory.connect('setup', self._setup_row)
        factory.connect('bind', self._bind_row)
        return factory

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

    @Gtk.Template.Callback()
    def _on_row_activated(self, _, index: int):
        self.current_index = index
        self.current_track = self.get_current_track()
        self.emit('jump-to-track')

    @Gtk.Template.Callback()
    def _remove_selected(self, _):
        """Remove the selected tracks from the queue. Sorts the selected indicies
        and removes segments of sequential indicies with splice() instead of
        each track individually, since splice() is much more efficent."""
        if not self.selected:
            return

        self._backup_queue()

        self.selected.sort()
        old_index = self.current_index
        segment, removed = [], 0
        for i in self.selected:
            self.current_index -= i < old_index
            # append to segment if the current i is sequential to the previous
            if not segment or i == segment[-1] + 1:
                segment.append(i)
            # when a non-sequential index is reached, splice the segment
            # of sequential inidices out of the queue and reset the segment
            else:
                self.model.splice(segment[0] - removed, len(segment), [])
                removed += len(segment)
                segment = [i]
        if segment:
            self.model.splice(segment[0] - removed, len(segment), [])
        self.selected = []
        self.select_all_button.set_active(False)
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
        self.select_all_button.set_inconsistent(
            self.select_all_button.get_active()
            and len(self.selected) != len(self.model)
        )

    def _backup_queue(self, save_index=False):
        # don't backup if the queue is empty (undoing to an empty queue
        # is annoying, and bothers me so I'm preventing it.)
        if self.model:
            backup = Gio.ListStore.new(TrackItem)
            backup.splice(0, len(backup), self.model)
            if save_index:
                self.backups.append((backup, self.current_index))
            else:
                self.backups.append((backup, None))

    def _restore_queue(self):
        if self.backups:
            backup, index = self.backups.pop()
            self.model.splice(0, len(self.model), backup)
            self.current_index = index or self.current_index


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
