from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi
from .library import TrackItem
from copy import copy

gi.require_version('Gtk', '4.0')


# TODO: Allow adding lone tracks to the queue. (Then allow for that in the UI)


class PlayQueue(Gtk.ListView):
    __gtype_name__ = 'RecordBoxPlayQueue'

    current_index = -1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = Gio.ListStore.new(TrackItem)
        self.selection_model = Gtk.MultiSelection.new(self.model)
        self.set_model(self.selection_model)

        self.factory = Gtk.BuilderListItemFactory.new_from_resource(
            Gtk.BuilderCScope(),
            '/com/github/edestcroix/RecordBox/lists/queue_row.ui',
        )
        self.set_factory(self.factory)

    loop = GObject.property(type=bool, default=False)

    def _setup_row(self, _, item):
        abin = Adw.Bin.new()
        row = Adw.ActionRow.new()
        abin.set_child(row)
        item.set_child(abin)
        item.set_selectable(False)

    def _bind_row(self, _, item):
        row = item.get_child().get_child()
        track = item.get_item()

        checkbox = Gtk.CheckButton()
        checkbox.set_css_classes(['selection-mode'])
        item.bind_property(
            'selected',
            checkbox,
            'active',
            GObject.BindingFlags.DEFAULT,
        )

        checkbox.connect(
            'toggled',
            self._select_action,
            item.get_position(),
        )

        if not row.get_title():
            row.add_prefix(checkbox)
        row.set_title(track.title)
        row.set_subtitle(track.length)

    def _select_action(self, button, value):
        print('Select action', value)
        if button.get_active():
            self.selection_model.select_item(value, False)
        else:
            self.selection_model.unselect_item(value)

    def add_album(self, album):
        for track in album.tracks:
            self.model.append(track)

    def start_selection(self):
        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', self._setup_row)
        factory.connect('bind', self._bind_row)
        self.set_factory(factory)

    def stop_selection(self):
        self.set_factory(self.factory)
        self.selection_model.unselect_all()

    def clear(self):
        self.model.remove_all()
        self.current_index = -1

    def empty_queue(self):
        self.clear()

    def restart(self):
        self.current_index = 0

    def empty(self):
        return self.current_index == -1

    def get_next_track(self):
        self.current_index += 1
        return self.get_current_track()

    def get_current_track(self):
        if self.current_index == -1 and len(self.model) > 0:
            self.current_index = 0
        return (
            self.model[self.current_index] if self.current_index >= 0 else None
        )

    def next(self):
        self._move_current('next')
        return 0 <= self.current_index < len(self.model)

    def previous(self):
        self._move_current('prev')
        return 0 <= self.current_index < len(self.model)

    def _move_current(self, direction, allow_none=False):
        if direction == 'next':
            if self.current_index > len(self.model) - 1:
                if self.loop:
                    self.current_index = 0
                elif allow_none:
                    self.current_index = -1
            else:
                self.current_index += 1
        elif direction == 'prev':
            if self.current_index <= 0:
                if allow_none:
                    self.current_index = -1
            else:
                self.current_index -= 1
