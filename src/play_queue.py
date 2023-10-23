from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi
from .library import TrackItem

gi.require_version('Gtk', '4.0')


# FIXME: Return-to-album no longer works when queue is empty because it requires getting
# the current album from the queue. Currently playing track should be stored somewhere.
class PlayQueue(Gtk.ListBox):
    __gtype_name__ = 'RecordBoxPlayQueue'

    current_index = -1
    # Set to true if the track at the currrent_index was removed, so that
    # advancing to the next track doesn't skip a track.
    current_index_moved = False

    loop = GObject.property(type=bool, default=False)
    _selection_active = False
    all_selected = GObject.Property(type=bool, default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = Gio.ListStore.new(TrackItem)
        self.bind_model(self.model, self._create_row, None, None)
        self.set_selection_mode(Gtk.SelectionMode.NONE)

    @GObject.Property(type=bool, default=False)
    def selection_active(self):
        return self._selection_active

    @selection_active.setter
    def set_selection_active(self, value):
        if value:
            self.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
            self._selection_active = True
        else:
            self.set_selection_mode(Gtk.SelectionMode.NONE)
            self._selection_active = False

    def add_album(self, album):
        for track in album.tracks:
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

    def clear(self):
        self.model.remove_all()
        self.current_index = -1

    def restart(self):
        self.current_index = 0

    def empty(self):
        return self.current_index == -1

    def get_next_track(self):
        if self.current_index_moved:
            self.current_index_moved = False
            return self.get_current_track()
        self._move_current('next')
        return self.get_current_track()

    def get_current_track(self):
        if self.current_index == -1 and len(self.model) > 0:
            self.current_index = 0
        return (
            self.model[self.current_index] if self.current_index >= 0 else None
        )

    def next(self):
        if self.current_index_moved:
            self.current_index_moved = False
        else:
            self._move_current('next', True)
        return 0 <= self.current_index < len(self.model)

    def previous(self):
        self._move_current('prev')
        if self.current_index_moved:
            self.current_index_moved = False
        return 0 <= self.current_index < len(self.model)

    def _create_row(self, item, __, _):
        row = Adw.ActionRow.new()
        row.set_title(item.title)
        row.set_subtitle(item.length)
        row.set_selectable(False)
        checkbox = Gtk.CheckButton()
        checkbox.set_valign(Gtk.Align.CENTER)
        checkbox.set_css_classes(['selection-mode'])
        checkbox.set_visible(self.selection_active)
        self.bind_property(
            'selection-active',
            checkbox,
            'visible',
            GObject.BindingFlags.DEFAULT,
        )
        self.bind_property(
            'all-selected',
            checkbox,
            'active',
            GObject.BindingFlags.DEFAULT,
        )
        # Don't want the row to be selectable if the checkbox is not selected,
        # so the only way to select the row is to click the checkbox.
        checkbox.bind_property(
            'active',
            row,
            'selectable',
            GObject.BindingFlags.DEFAULT,
        )
        checkbox.connect(
            'toggled',
            self._select_action,
            row,
        )
        checkbox.connect('hide', lambda b: b.set_active(False))
        row.add_prefix(checkbox)

        return row

    def _select_action(self, button, row):
        if not self.selection_active:
            return
        if button.get_active():
            row.set_selectable(True)
            self.select_row(row)
        else:
            row.set_selectable(False)
            self.unselect_row(row)

    def _move_current(self, direction, allow_none=False):
        if direction == 'next':
            if self.current_index >= len(self.model) - 1:
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
