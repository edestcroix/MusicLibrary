from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi
from .library import AlbumItem, TrackItem
from enum import Enum


Direction = Enum('Direction', 'NEXT PREV')

gi.require_version('Gtk', '4.0')


# TODO: Combine the PlayQueue and PlayQueueList classes.


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

    queue_header = Gtk.Template.Child()
    delete_selected = Gtk.Template.Child()

    _selection_active = False

    jump_to_track = GObject.Signal()

    current_index = GObject.Property(type=int, default=-1)
    current_index_moved = False
    current_track = GObject.Property(type=TrackItem)

    jump_to_track = GObject.Signal()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.model = Gio.ListStore.new(TrackItem)
        self.selection = Gtk.MultiSelection.new(self.model)
        self.no_selection = Gtk.NoSelection.new(self.model)

        self.track_list.set_model(self.no_selection)
        self.track_list.set_factory(self._create_factory())

        self.track_list.connect('activate', self._on_row_activated)

        self.delete_selected.set_sensitive(True)

        self.select_all_button.connect('clicked', lambda _: self.select_all())

    def _create_factory(self):
        factory = Gtk.SignalListItemFactory.new()
        factory.connect('setup', self._setup_row)
        factory.connect('bind', self._bind_row)
        return factory

    @GObject.Property(type=bool, default=False)
    def selection_active(self):
        return self._selection_active

    @selection_active.setter
    def set_selection_active(self, value: bool):
        self.unselect_all()
        self._selection_active = value
        if value:
            self.track_list.set_model(self.selection)
            self.queue_header.set_css_classes(['header-accent'])
        else:
            self.track_list.set_model(self.no_selection)
            self.queue_header.set_css_classes([])
        # Trigger the notify::current-track callback in the queue rows so the current track
        # highlight persists across the selection model changing.
        self.current_index = self.current_index

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
    def _on_queue_toggle(self, _):
        self.set_property('selection-active', False)
        # tell the main view that the queue should be closed
        self.emit('collapse')

    @Gtk.Template.Callback()
    def _remove_selected(self, _):
        i = 0
        while i < len(self.model):
            if self.selection.is_selected(i):
                self.model.remove(i)
                if i == self.current_index:
                    self.current_index_moved = True
                elif i < self.current_index:
                    self.current_index -= 1
                    self.current_track = self.get_current_track()
            else:
                i += 1

    def _move_current(self, direction: Direction):
        if direction == Direction.NEXT:
            self.current_index += 1
        elif direction == Direction.PREV:
            if self.current_index >= len(self.model):
                self.current_index = len(self.model) - 2
            else:
                self.current_index -= 1

    def _on_row_activated(self, _, index: int):
        if not self.selection_active:
            self.current_index = index
            self.current_track = self.get_current_track()
            self.emit('jump-to-track')

    def _setup_row(self, _, item):
        row = QueueRow()
        item.set_child(row)
        item.bind_property(
            'selected',
            row.checkbutton,
            'active',
            GObject.BindingFlags.DEFAULT,
        )
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
    position = GObject.Property(type=int)

    # Each row knows the current index so it can highlight itself when it's the current track.
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
