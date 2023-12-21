from collections import deque
from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi
from collections import defaultdict
from .items import TrackItem, AlbumItem, QueueItem

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

    selected: set[int] = set()

    def __init__(self):
        super().__init__()

        self.base_model = Gio.ListStore.new(QueueItem)
        self.tree_model = Gtk.TreeListModel.new(
            self.base_model,
            passthrough=False,
            autoexpand=False,
            create_func=self._child_model,
        )
        self.tree_model.connect(
            'notify::n-items', lambda *_: self._update_current_highlight()
        )
        self.selection = Gtk.MultiSelection.new(self.tree_model)
        self.selection.connect('selection-changed', self._check_selection)

        self.track_list.set_model(self.selection)
        self.track_list.set_factory(self._create_factory())

        # flatten tree layout into a single list by mapping
        # every item in model to a ListModel of it's children (or itself if it has none)
        model_map = Gtk.MapListModel.new(self.base_model, self._map_to_model)
        # then put this list of models into a FlattenListModel to make the actual queue
        self.queue = Gtk.FlattenListModel.new(model_map)

        self.backups = deque(maxlen=10)

    def append_album(self, album: AlbumItem):
        album = QueueItem(album)
        self._backup_queue()
        self.base_model.append(album)
        self._update_positions()

    def overwrite_album(self, album: AlbumItem):
        album = QueueItem(album)
        self._backup_queue(save_index=True)
        self.base_model.splice(0, len(self.base_model), [album])
        self._reset(empty=False)
        self._update_positions()

    def append(self, tracks: list[TrackItem]):
        tracks = [QueueItem(t) for t in tracks]
        self._backup_queue()
        self.base_model.splice(len(self.base_model), 0, tracks)
        self._update_positions()

    def overwrite(self, tracks: list[TrackItem]):
        tracks = [QueueItem(t) for t in tracks]
        self._backup_queue(save_index=True)
        self.base_model.splice(0, len(self.base_model), tracks)
        self._reset(empty=False)
        self._update_positions()

    def set_index(self, index: int):
        # We want to avoid setting the current_index value
        # as much as possible because it triggers a reload of the current
        # track css which can crash GTK if done too frequently.
        if index != self.current_index:
            self.current_index = index

        current = self.queue[self.current_index]
        for row in self.tree_model:
            if not row:
                return
            item = row.get_item()
            if children := item.children:
                if current in children:
                    row.set_expanded(True)
                else:
                    row.set_expanded(False)
            else:
                row.set_expanded(False)

    # TODO: Redo?
    def undo(self, *_):
        self._restore_queue()

    def select_all(self):
        self.selection.select_all()

    def unselect_all(self):
        self.selection.unselect_all()

    def clear(self):
        self.base_model.remove_all()
        self._reset()

    def restart(self):
        self.current_index = 0

    def is_empty(self) -> bool:
        return len(self.base_model) == 0

    def index_synced(self) -> bool:
        """Checks if the current_track and the track at current_index are the same.
        When they are not, it means the current track was changed outside of normal
        queue advancement like get_next_track(), jumping to a track, or next() and previous().
        (E.g the current track was deleted from the queue or a restored backup changed current_index)"""
        return (
            self.queue
            and 0 <= self.current_index < len(self.queue)
            and self.current_track == self.queue[self.current_index]
        )

    def get_next_track(self) -> TrackItem | None:
        self.next()
        return self.get_current_track()

    def get_current_track(self) -> TrackItem | None:
        """Retrieves the current track from the queue, and sets self.current_track
        to the value retrieved. Uses self.current_index to determine the track to
        get, meaning that if the two values are unsynced, they will resync after the next call
        to this method."""

        # An index of -1 is used to inidicate to the previous()
        # function that the queue was already at the start. If the
        # queue isn't empty then it should be considered a 0.

        if self.current_index == -1 and len(self.queue) > 0:
            self.current_index = 0
        if 0 <= self.current_index < len(self.queue):
            if self.current_track != self.queue[self.current_index]:
                self.current_track = self.queue[self.current_index]
        else:
            self.current_track = None
        return self.current_track

    def next(self) -> bool:
        # Only advance if the index is synced, because otherwise
        # the next track is already at the current index
        if self.index_synced():
            # use set_index here because we don't want to trigger
            # the current_index::notify signal if the value doesn't change
            self.set_index(min(self.current_index + 1, len(self.queue)))
        return 0 <= self.current_index < len(self.queue)

    def previous(self) -> bool:
        if self.current_index >= len(self.queue):
            self.current_index = len(self.queue) - 1
        self.set_index(max(self.current_index - 1, 0))
        return 0 <= self.current_index < len(self.queue)

    @Gtk.Template.Callback()
    def toggle_selection(self, button):
        if button.get_active():
            self.select_all()
        else:
            self.unselect_all()

    def remove_backups(self):
        self.backups.clear()

    @Gtk.Template.Callback()
    def _on_row_activated(self, _, index: int):
        total = 0
        for i, row in enumerate(self.tree_model):
            if i == index:
                break
            if not (item := row.get_item()).from_album:
                total += 1
            elif not row.get_expanded():
                total += len(item.children)

        self.set_index(total)
        self.get_current_track()
        self.emit('jump-to-track')

    @Gtk.Template.Callback()
    def _remove_selected(self, _):
        if not self.selected:
            return
        self._backup_queue()

        removals = defaultdict(list)
        bulk_removes = []
        count = 0
        for i in range(len(self.base_model)):
            row = self.tree_model.get_child_row(i)
            item = row.get_item()
            if row.get_expanded():
                for j in range(len(item.children)):
                    count += 1
                    if self.selection.is_selected(count):
                        removals[i].append(j)
                if len(removals[i]) == len(item.children):
                    # TODO: In this case, the current index needs to be
                    # decreased by however many of the children in this
                    # album are selected that are before the current index
                    bulk_removes.append(i)
                    del removals[i]
            elif self.selection.is_selected(count):
                # TODO: Same here
                bulk_removes.append(i)
            count += 1

        for removed, i in enumerate(bulk_removes):
            self.base_model.remove(i - removed)

        for k, v in removals.items():
            if v:
                item = self.tree_model.get_child_row(k).get_item()
                self._splice_out_sequential(item.children, v)

        self.selection.unselect_all()
        self.selected.clear()
        self._update_positions()

    def _splice_out_sequential(self, model, selected: list[int]):
        # group selected indicies into sequential segments
        old_index = self.current_index
        segment = []
        removed = 0
        for i in selected:
            self.current_index -= i < old_index
            # append to segment if the current i is sequential to the previous
            if not segment or i == segment[-1] + 1:
                segment.append(i)
            # when a non-sequential index is reached, splice the segment
            # of sequential inidices out of the queue and reset the segment
            else:
                model.splice(segment[0] - removed, len(segment), [])
                removed += len(segment)
                segment = [i]

        if segment:
            model.splice(segment[0] - removed, len(segment), [])
            removed += len(segment)

        return removed

    def _reset(self, empty=True):
        """Puts queue state variables and widgets back to the default start state.
        Used when the queue is cleared or overwritten."""
        self.selected.clear()
        self.current_index = -1 if empty else 0
        self._update_selection_controls()

    def _check_selection(self, _, start, range_size):
        """Maintain a list of selected rows so we can delete them later.
        (Could just iterate over the list to find selected items on delete, but this
        way the delete button's sensitivity can be updated too."""
        for i in range(start, start + range_size):
            if self.selection.is_selected(i):
                self.selected.add(i)
            elif i in self.selected:
                self.selected.remove(i)
        self._update_selection_controls()

    def _update_selection_controls(self):
        self.delete_selected.set_sensitive(len(self.selected) > 0)
        self.select_all_button.set_inconsistent(
            self.select_all_button.get_active()
            and len(self.selected) != len(self.tree_model)
        )

    def _backup_queue(self, save_index=False):
        # don't backup if the queue is empty (undoing to an empty queue
        # is annoying, and bothers me so I'm preventing it.)
        if self.base_model:
            backup = Gio.ListStore.new(TrackItem)
            backup.splice(0, len(backup), self.base_model)
            if save_index:
                self.backups.append((backup, self.current_index))
            else:
                self.backups.append((backup, None))

    def _restore_queue(self):
        if self.backups:
            backup, index = self.backups.pop()
            self.base_model.splice(0, len(self.base_model), backup)
            self.current_index = index or self.current_index

    def _create_factory(self):
        factory = Gtk.SignalListItemFactory.new()
        factory.connect('setup', self._setup_row)
        factory.connect('bind', self._bind_row)
        return factory

    def _setup_row(self, _, item):
        expander = Gtk.TreeExpander.new()
        row = QueueRow()
        expander.set_child(row)
        item.set_child(expander)

    def _bind_row(self, _, item):
        expander = item.get_child()
        queue_row = expander.get_child()
        row = item.get_item()
        expander.set_list_row(row)
        obj = row.get_item()

        self.bind_property(
            'current-index',
            queue_row,
            'current-index',
            GObject.BindingFlags.DEFAULT,
        )

        queue_row.title = obj.raw_title
        queue_row.subtitle = obj.subtitle
        queue_row.image_path = obj.thumb
        queue_row.is_album = obj.from_album
        if not queue_row.is_album:
            obj.bind_property(
                'position',
                queue_row,
                'position',
                GObject.BindingFlags.DEFAULT
                | GObject.BindingFlags.SYNC_CREATE,
            )

    def _child_model(self, item: QueueItem):
        if not item:
            return None
        return children if (children := item.children) else None

    def _update_current_highlight(self):
        # trigger the notify signal for current_index to update the current track highlight
        # whenever a row is expaned in the play queue. (The newly created rows won't update
        self.current_index = self.current_index
        self.selected.clear()
        self.selection.unselect_all()

    def _map_to_model(self, item: QueueItem) -> Gio.ListModel:
        if children := item.children:
            if len(children) == 0:
                children.append(item)
            return children
        store = Gio.ListStore.new(QueueItem)
        store.append(item)
        return store

    def _update_positions(self, *_):
        # TODO: Make sure this is occuring every time the queue is changed, and
        # that the change is propagated everywhere it needs to be (The QueueItems)
        for i, item in enumerate(self.queue):
            item.position = i
        self._update_current_highlight()


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

    is_album = GObject.Property(type=bool, default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('notify::current-index', self._check_current)

    def _check_current(self, *_):
        if self.is_album:
            return
        if (expander := self.get_parent()) and (
            listrow := expander.get_parent()
        ):
            if self.current_index == self.position:
                listrow.set_name('current-track')
            elif listrow.get_name() == 'current-track':
                listrow.set_name('')
