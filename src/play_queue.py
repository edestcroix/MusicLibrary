from collections import deque, defaultdict
import gi
from gi.repository import Adw, Gtk, GLib, GObject, Gio
from itertools import chain
from .items import TrackItem, AlbumItem, QueueItem

gi.require_version('Gtk', '4.0')


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/play_queue.ui')
class PlayQueue(Adw.Bin):
    __gtype_name__ = 'RecordBoxPlayQueue'
    """A containter for the play queue, containing the entire view around the track list itself,
    and the operations to manage the queue and maintain current track state."""

    track_list = Gtk.Template.Child()
    delete_selected = Gtk.Template.Child()

    can_undo = GObject.Property(type=bool, default=False)
    can_redo = GObject.Property(type=bool, default=False)

    empty = GObject.Property(type=bool, default=True)

    current_index = GObject.Property(type=int, default=-1)
    current_track = GObject.Property(type=TrackItem)

    jump_to_track = GObject.Signal()

    def __init__(self):
        super().__init__()

        self._base_model = Gio.ListStore.new(QueueItem)
        self._base_model.connect('items-changed', self._update_queue)
        self._tree_model = Gtk.TreeListModel.new(
            self._base_model,
            passthrough=False,
            autoexpand=False,
            create_func=self._child_model,
        )
        self._selection = Gtk.MultiSelection.new(self._tree_model)

        self.track_list.set_model(self._selection)
        self.track_list.set_factory(self._create_factory())

        self._queue = []

        self._backups = deque(maxlen=10)
        self._redos = deque(maxlen=10)

    def append_album(self, album: AlbumItem):
        album = QueueItem(**album.for_queue())
        self._backup_queue()
        self._base_model.append(album)

    def append(self, tracks: list[TrackItem]):
        tracks = [QueueItem(**dict(t)) for t in tracks]
        self._backup_queue()
        self._base_model.splice(len(self._base_model), 0, tracks)

    def overwrite_w_album(self, album: AlbumItem, start: int = 0):
        album = QueueItem(**album.for_queue())
        self._backup_queue(save_index=True)
        self._base_model.splice(0, len(self._base_model), [album])
        self._reset(empty=False)
        self.set_index(start)
        self._update_current_parent(self._queue[self.current_index])

    def overwrite_w_tracks(self, tracks: list[TrackItem], start: int = 0):
        self._backup_queue(save_index=True)
        self._base_model.splice(
            0, len(self._base_model), [QueueItem(**dict(t)) for t in tracks]
        )
        self._reset(empty=False)
        self.set_index(start)
        self._update_current_parent(self._queue[self.current_index])

    def insert(self, track: TrackItem):
        track = QueueItem(**dict(track))
        self._backup_queue()
        # find the index of the current_track in the base model (either it's own index in that model
        # if it's a root, or the index of it's parent in that model if it's a child)
        if self.current_track in self._base_model:
            # if the current_track is a root, insert the new track after it
            index = list(self._base_model).index(self.current_track)
            self._base_model.insert(index + 1, track)
            return
        # iterate through children lists of root items until the current_track is found
        for i, item in enumerate(list(self._base_model)):
            if item.children and self.current_track in item.children:
                index = list(item.children).index(self.current_track)
                if index == len(item.children) - 1:
                    self._base_model.insert(i + 1, track)
                    break
                # split the root into two (duplicate it into a new QueueItem,
                # everything up to the current_track stays, new one gets everything after,
                # put the new one after the old one)
                new = item.clone(children=item.children[index + 1 :])
                item.children.splice(
                    index + 1, len(item.children) - index - 1, []
                )
                self._base_model.splice(i + 1, 0, [track, new])
                break

        self._update_queue()
        self._update_current_parent(self.current_track)

    def set_index(self, index: int):
        self.current_index = index
        self._update_queue(items_changed=False)

    def next(self) -> bool:
        if (
            self.empty
            or self.current_index < 0
            or self.current_index >= len(self._queue) - 1
        ):
            return False

        if self.current_track == self._queue[self.current_index]:
            self.current_index += 1
        return True

    def previous(self) -> bool:
        if self.current_index == 0 or self.empty:
            return False
        # if the current index is greater than the length of the queue, move it to the last index
        elif self.current_index > len(self._queue) - 1:
            self.current_index = len(self._queue) - 1
        else:
            self.current_index -= 1
        return True

    def get_current_track(self, update=True) -> QueueItem | None:
        if self.current_index == -1 and not self.empty:
            self.current_index = 0
        if update:
            self.current_track = self._queue[self.current_index]
            self._update_current_parent(self.current_track)
            self._update_queue(items_changed=False)
        return self.current_track

    def get_next_track(self) -> TrackItem | None:
        if self.next():
            return self.get_current_track()

    def clear(self):
        self._base_model.remove_all()
        self._reset()

    def restart(self):
        self.set_index(0)

    def remove_backups(self):
        self._backups.clear()
        self._redos.clear()
        self.can_undo = False
        self.can_redo = False

    @Gtk.Template.Callback()
    def undo(self, *_):
        if self._backups:
            # add current queue to redo stack
            self._backup_queue(redo=True, clear_redo=False)

            backup, index = self._backups.pop()
            self._base_model.splice(0, len(self._base_model), backup)
            self.set_index(index or self.current_index)
            self.can_undo = len(self._backups) > 0
        else:
            self.can_undo = False

        self.can_redo = len(self._redos) > 0
        if self.current_index < len(self._queue):
            self._update_current_parent(self._queue[self.current_index])

    @Gtk.Template.Callback()
    def redo(self, *_):
        if self._redos:
            # add current queue to undo stack
            self._backup_queue(clear_redo=False)

            backup, index = self._redos.pop()
            self._base_model.splice(0, len(self._base_model), backup)
            self.set_index(index or self.current_index)
            self.can_redo = len(self._redos) > 0
        else:
            self.can_redo = False

        self.can_undo = len(self._backups) > 0
        if self.current_index < len(self._queue):
            self._update_current_parent(self._queue[self.current_index])

    @Gtk.Template.Callback()
    def select_all(self, *_):
        self._selection.select_all()

    @Gtk.Template.Callback()
    def unselect_all(self, *_):
        self._selection.unselect_all()

    @Gtk.Template.Callback()
    def _on_row_activated(self, _, index: int):
        total = 0
        for i, row in enumerate(self._tree_model):
            if i == index:
                break
            if not (item := row.get_item()).from_album:
                total += 1
            elif not row.get_expanded():
                total += len(item.children)

        self.set_index(total)
        self.emit('jump-to-track')

    @Gtk.Template.Callback()
    def _remove_selected(self, _):
        """Removes selected tracks from the queue. Surprisingly complicated;
        the selection model operates on the tree model, so the indicies of the selected
        rows are not the same as the indicies of the rows within the children lists of root items,
        and the actual queue uses a different indexing again. (If the queue was just a flat list all
        that would need to be done is call _splice_out_sequential() on the list model)"""
        if self._selection.get_selection().is_empty():
            return
        self._backup_queue(save_index=True)

        bulk_removes, removals, index_delta = self._find_removals()

        self._splice_out_sequential(self._base_model, bulk_removes)

        removed = len(bulk_removes)
        # delete children from the rows that weren't fully deleted.
        for k, v in removals.items():
            if v and (
                item := self._tree_model.get_child_row(
                    max(0, k - removed)
                ).get_item()
            ):
                self._splice_out_sequential(item.children, v)

        self.current_index -= index_delta
        self._update_queue()

    def _find_removals(self) -> tuple[list[int], dict, int]:
        """Evaluates the currently selected rows in the queue to determine what should be removed.
        Maps the indexes of the selected rows in tree_model to their indexes in base_model or their indexes
        in their parent's children list. (The selection model operates on the tree model, but the items have
        to be removed at the base model level, or the children list level.)
        Returns a tuple of:
            bulk_removes: list of root indicies that can be removed wholesale
            removals: dict of root indicies which have some children to remove, and the indicies of said children
                within that root's children list
            index_delta: the total number of tracks removed before the current track
        """

        # dict of root indicies which have some children to remove, and the indicies of said children
        removals = defaultdict(list)
        # bulk_removes is the root indicies of rows that can just be removed wholesale (all children selected)
        # count is the index of the visible row in the queue, because that's what the selection model uses
        # index_delta is the number of tracks removed before the current track
        bulk_removes, count, index_delta = [], 0, 0
        for root_index in range(len(self._base_model)):
            row = self._tree_model.get_child_row(root_index)
            children = row.get_item().children
            # only expanded rows are able to have children selected
            if row.get_expanded():
                # so if expanded, figure out the indexes of the selected children
                for child_index in range(len(children)):
                    count += 1
                    if self._selection.is_selected(count):
                        removals[root_index].append(child_index)
                        index_delta += (
                            children[child_index].position < self.current_index
                        )
                if len(removals[root_index]) == len(children):
                    bulk_removes.append(root_index)
                    del removals[root_index]
            # if the row isn't expanded, and selected, add it to the bulk remove list
            elif self._selection.is_selected(count):
                bulk_removes.append(root_index)
                # then figure out how many tracks will be removed before the current track
                if children:
                    found, index = children.find(self.current_track)
                    if found:
                        index_delta += index
                    elif children[-1].position < self.current_index:
                        index_delta += len(children)
                # lone tracks (no children) can be in the top-level queue, check for that.
                elif row.get_item().position < self.current_index:
                    index_delta += 1
            count += 1

        return bulk_removes, removals, index_delta

    def _splice_out_sequential(self, model, selected: list[int]):
        segment, removed = [], 0
        for i in selected:
            # append to segment if the current i is sequential to the previous
            if not segment or i == segment[-1] + 1:
                segment.append(i)
            # when a non-sequential index is reached, splice the segment
            # of sequential inidices out of the queue and reset the segment
            else:
                model.splice(segment[0] - removed, len(segment), [])
                removed += len(segment)
                segment = [i]
        # the last segment is never spliced in the loop, so splice it here
        if segment:
            model.splice(segment[0] - removed, len(segment), [])
            removed += len(segment)

    def _update_queue(self, *_, items_changed=True):
        if items_changed:
            self._queue = list(
                chain.from_iterable(
                    item.children or [item] for item in self._base_model
                )
            )
        for i, item in enumerate(self._queue):
            item.position = i
            if item.is_current and i != self.current_index:
                item.is_current = False
            elif i == self.current_index:
                item.is_current = True

        self.empty = len(self._queue) == 0

    def _update_current_parent(self, current: QueueItem, expand=True):
        for i in range(len(self._base_model)):
            if row := self._tree_model.get_child_row(i):
                item = row.get_item()
                if not item.from_album:
                    continue
                if current in item.children:
                    if expand and not row.get_expanded():
                        row.set_expanded(True)
                    item.is_current = True
                elif item.is_current:
                    if expand and row.get_expanded():
                        row.set_expanded(False)
                    # got to add a timeout apparently because states don't properly
                    # update while the rows are being expanded/collapsed
                    GLib.timeout_add(
                        25, item.set_property, 'is-current', False
                    )

    def _reset(self, empty=True):
        """Puts queue state variables and widgets back to the default start state.
        Used when the queue is cleared or overwritten."""
        self.current_index = -1 if empty else 0

    def _backup_queue(self, redo=False, save_index=False, clear_redo=True):
        # don't backup if the queue is empty (undoing to an empty queue
        # is annoying, and bothers me so I'm preventing it.)
        if self._base_model:
            if clear_redo:
                self._redos.clear()
            backup = Gio.ListStore.new(QueueItem)
            backup.splice(
                0, len(backup), [i.clone() for i in self._base_model]
            )
            if redo:
                self._redos.append(
                    (backup, self.current_index if save_index else None)
                )
            else:
                self._backups.append(
                    (backup, self.current_index if save_index else None)
                )

        self.can_undo = len(self._backups) > 0
        self.can_redo = len(self._redos) > 0

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

        queue_row.title = obj.title
        queue_row.subtitle = obj.subtitle
        obj.bind_property(
            'subtitle',
            queue_row,
            'subtitle',
            GObject.BindingFlags.DEFAULT,
        )
        queue_row.image_path = obj.thumb
        queue_row.is_album = obj.from_album
        obj.bind_property(
            'is-current',
            queue_row,
            'is-current',
            GObject.BindingFlags.DEFAULT,
        )
        if obj.is_current:
            # need some delay otherwise GTK will crash (css is being set before the widget
            # is is fully constructed or something)
            GLib.timeout_add(25, queue_row.set_property, 'is-current', True)

    def _child_model(self, item: QueueItem):
        if not item:
            return None
        return children if (children := item.children) else None


@Gtk.Template(
    resource_path='/com/github/edestcroix/RecordBox/lists/queue_row.ui'
)
class QueueRow(Adw.Bin):
    """Really basic wrapper around the UI file that could be used
    with a BuilderListItemFactory if we didn't need to bind the current-index"""

    __gtype_name__ = 'RecordBoxQueueRow'
    current_index = GObject.Property(type=int)

    is_current = GObject.Property(type=bool, default=False)

    title = GObject.Property(type=str)
    subtitle = GObject.Property(type=str)
    image_path = GObject.Property(type=str)

    is_album = GObject.Property(type=bool, default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('notify::is-current', self._check_current)

    def _check_current(self, *_):
        if not (expander := self.get_parent()) or not (
            listrow := expander.get_parent()
        ):
            return
        if self.is_current:
            listrow.set_name('current-track')
        elif listrow.get_name() == 'current-track':
            listrow.set_name('')
