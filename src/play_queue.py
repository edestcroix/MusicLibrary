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

        self.track_list.connect(
            'selected-rows-changed',
            lambda _: self.delete_selected.set_sensitive(
                len(self.track_list.get_selected_rows()) > 0
            ),
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


class PlayQueueList(Gtk.ListBox):
    """A ListBox that contains the track list of the play queue, and
    implements the functionality for tracking and advancing the current track,
    and functions for removing tracks from the list. Implements a selection
    mode that allows selecting tracks to remove."""

    __gtype_name__ = 'RecordBoxPlayQueueList'

    current_index = -1
    # Set to true if the track at the currrent_index was removed, so that
    # advancing to the next track doesn't skip a track.
    current_index_moved = False
    current_track = GObject.Property(type=TrackItem)

    loop = GObject.property(type=bool, default=False)
    _selection_active = False
    all_selected = GObject.Property(type=bool, default=False)
    jump_to_track = GObject.Signal()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = Gio.ListStore.new(TrackItem)
        self.bind_model(self.model, self._create_row, None, None)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_activate_on_single_click(False)

        self.connect('row-activated', self._on_row_activated)

    @GObject.Property(type=bool, default=False)
    def selection_active(self):
        return self._selection_active

    @selection_active.setter
    def set_selection_active(self, value: bool):
        self.unselect_all()
        self.set_activate_on_single_click(value)
        self._selection_active = value
        if value:
            self.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        else:
            self.set_selection_mode(Gtk.SelectionMode.NONE)
            self.all_selected = False

    def add_album(self, album: AlbumItem):
        for track in album.tracks:
            self.model.append(track)

    def add_track(self, track: TrackItem):
        self.model.append(track)

    def remove_selected(self):
        for row in self.get_selected_rows():
            if row.get_index() < self.current_index:
                self.current_index -= 1
            elif row.get_index() == self.current_index:
                self.current_index_moved = True
            self.model.remove(row.get_index())
        if len(self.model) == 0:
            self.current_index = -1
        self.all_selected = False

    def clear(self):
        self.model.remove_all()
        self.current_index = -1

    def restart(self):
        self.current_index = 0

    def empty(self) -> bool:
        return self.current_index == -1

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
        self._highlight_current()
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

    def _create_row(self, item: TrackItem, __, _) -> Adw.ActionRow:
        """Callback for the ListBox's bind_model method to create row widgets for
        newly added items to the model. Returns an Adw.ActionRow with a hidden
        checkbox that can be used to select the row. Checkbox will become visible on
        enabling selection mode."""
        artists = (
            f'{item.albumartist}, {item.artists}'
            if item.artists
            else item.albumartist
        )
        artists = GLib.markup_escape_text(artists)
        row = Adw.ActionRow(
            title=item.title,
            subtitle=f'{item.length} - {artists}',
            css_classes=['queue-row'],
        )
        checkbox = Gtk.CheckButton(
            valign=Gtk.Align.CENTER,
            visible=False,
            css_classes=['selection-mode'],
        )
        image = Gtk.Image.new_from_file(item.thumb)
        image.set_pixel_size(32)
        row.add_prefix(image)
        row.add_prefix(checkbox)
        self._bind_row(row, checkbox, image)
        return row

    def _bind_row(
        self, row: Adw.ActionRow, checkbox: Gtk.CheckButton, image: Gtk.Image
    ):
        """Binds the necessary properties to implement the selection mode, by
        connection the checkbox's toggled state to the selection of the row,
        allowing selection to be toggled by clicking on the row when the select mode
        is active. Also set up so selection state resets when selection mode toggles."""

        self.bind_property(
            'selection-active',
            checkbox,
            'visible',
            GObject.BindingFlags.DEFAULT,
        )

        self.bind_property(
            'selection-active',
            image,
            'visible',
            GObject.BindingFlags.INVERT_BOOLEAN,
        )

        # Enabling all-selected activates all checkboxes; default binding
        # allows the checkbox to be (de)activated independently of the all-selected property.
        self.bind_property(
            'all-selected',
            checkbox,
            'active',
            GObject.BindingFlags.DEFAULT,
        )

        # Bind the checkbox to a callback to select the row when active
        checkbox.connect(
            'toggled',
            self._select_action,
            row,
        )
        # and also bind the list to toggle checkboxes when rows are selected,
        # to make sure selection state and checkbox state are always in sync
        # (ListBoxRows don't have a 'selected' property to bind to)
        self.connect(
            'selected-rows-changed',
            self._selection_changed,
            row,
            checkbox,
        )
        row.set_activatable_widget(checkbox)
        # makes sure checkboxes are reset when selection mode is toggled
        checkbox.connect('hide', lambda b: b.set_active(False))
        checkbox.connect('show', lambda b: b.set_active(False))

    def _select_action(self, button: Gtk.CheckButton, row: Adw.ActionRow):
        if not self.selection_active:
            return
        if button.get_active():
            self.select_row(row)
        else:
            self.unselect_row(row)

    def _selection_changed(
        self, _, row: Adw.ActionRow, checkbox: Gtk.CheckButton
    ):
        if checkbox.get_active():
            checkbox.set_active(row.is_selected())

    def _move_current(self, direction: str, allow_none=False):
        self._unhighlight_current()
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

    def _highlight_current(self):
        if 0 <= self.current_index < len(self.model):
            current_row = self.get_row_at_index(self.current_index)
            self._add_css(current_row, 'current-track')

    def _unhighlight_current(self):
        if 0 <= self.current_index < len(self.model):
            current_row = self.get_row_at_index(self.current_index)
            self._remove_css(current_row, 'current-track')

    def _add_css(self, obj: Gtk.Widget, class_name: str):
        obj.set_css_classes(obj.get_css_classes() + [class_name])

    def _remove_css(self, obj: Gtk.Widget, class_name: str):
        obj.set_css_classes(
            [c for c in obj.get_css_classes() if c != class_name]
        )

    def _on_row_activated(self, _, row: Adw.ActionRow):
        if not self.selection_active:
            # jump to track in queue
            self._unhighlight_current()
            self.current_index = row.get_index()
            self.current_track = self.get_current_track()
            self._highlight_current()
            self.emit('jump-to-track')
