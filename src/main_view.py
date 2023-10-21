# window.py
#
# Copyright 2023 Emmett de St. Croix
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from copy import copy
from gi.repository import Adw, Gtk, GLib, Gst, Gio, GObject
import gi
from .library import AlbumItem
from .album_view import RecordBoxAlbumView
from .player_controls import RecordBoxPlayerControls
from .player import Player
from .monitor import ProgressMonitor

gi.require_version('Gtk', '4.0')
gi.require_version('Gst', '1.0')


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/main_view.ui')
class MainView(Adw.Bin):
    __gtype_name__ = 'MainView'

    album_overview = Gtk.Template.Child()

    toolbar_view = Gtk.Template.Child()

    play = Gtk.Template.Child()
    queue_toggle = Gtk.Template.Child()
    queue_panel_split_view = Gtk.Template.Child()
    queue_add = Gtk.Template.Child()
    play_queue = Gtk.Template.Child()

    return_to_album = Gtk.Template.Child()

    lists_toggle = Gtk.Template.Child()

    player_controls = Gtk.Template.Child()

    toast = Gtk.Template.Child()

    confirm_play = GObject.Property(type=bool, default=True)
    clear_queue = GObject.Property(type=bool, default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.player = Player(self.play_queue)
        self.player_controls.attach_to_player(self.player)
        self.player_controls.loop.bind_property(
            'active',
            self.play_queue,
            'loop',
            GObject.BindingFlags.BIDIRECTIONAL,
        )

        self._setup_actions()
        self._set_controls_stopped()

    album_changed = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    def set_breakpoint(self, _, breakpoint_num):
        self.album_overview.set_breakpoint(None)
        if breakpoint_num > 2:
            self.lists_toggle.set_visible(True)

    def unset_breakpoint(self, _, breakpoint_num):
        self.album_overview.unset_breakpoint(None)
        if breakpoint_num > 2:
            self.lists_toggle.set_visible(False)

    def update_album(self, album: AlbumItem, current_artist=None):
        self.album_overview.update_album(album, current_artist)
        self.play.set_sensitive(True)
        self.queue_add.set_sensitive(True)

    def send_toast(self, title, timeout=2):
        toast = Adw.Toast()
        toast.set_title(title)
        toast.set_timeout(timeout)
        self.toast.add_toast(toast)

    def _setup_actions(self):
        self.player.connect('stream_start', self._on_stream_start)
        self.player.connect('state-changed', self._on_player_state_changed)

    @Gtk.Template.Callback()
    def _on_play(self, _):
        if not (album := self.album_overview.current_album):
            return
        if self.player.state == 'stopped' or not self.confirm_play:
            self._play_album(album)
        else:
            self._confirm_album_play(album, album.name)

    @Gtk.Template.Callback()
    def _on_queue_add(self, _):
        if album := self.album_overview.current_album:
            self.play_queue.add_album(album)
            if self.player.state == 'stopped':
                self.player.ready()
            self.send_toast('Queue Updated')

    @Gtk.Template.Callback()
    def _on_queue_clear(self, _):
        self.play_queue.empty_queue()

    @Gtk.Template.Callback()
    def _on_play_track(self, _, track_album: AlbumItem):
        # selected track to play is returned in an AlbumItem
        # containing only that specific track, because play queue currently
        # doesn't support adding individual tracks.
        if self.player.state == 'stopped' or not self.confirm_play:
            self._play_album(track_album)
        else:
            self._confirm_album_play(track_album, track_album.tracks[0].title)

    @Gtk.Template.Callback()
    def _on_add_track(self, _, track_album):
        self.play_queue.add_album(track_album)
        if self.player.state == 'stopped':
            self.player.ready()
        self.send_toast('Queue Updated')

    @Gtk.Template.Callback()
    def _on_queue_toggle(self, _):
        self.queue_panel_split_view.set_show_sidebar(
            not self.queue_panel_split_view.get_show_sidebar()
        )

    @Gtk.Template.Callback()
    def _on_return_to_album(self, _):
        if self.play_queue.current_track:
            current_album = self.play_queue.get_current_track().album
            self.emit('album_changed', current_album)

    @Gtk.Template.Callback()
    def _skip_forward(self, _):
        if self.play_queue.next():
            self.player.play()

    @Gtk.Template.Callback()
    def _skip_backward(self, _):
        if self.play_queue.previous():
            self.player.play()

    @Gtk.Template.Callback()
    def _stop(self, _):
        self.player.stop()

    @Gtk.Template.Callback()
    def _toggle_play(self, _):
        self.player.toggle()

    def _confirm_album_play(self, album, name):
        dialog = Adw.MessageDialog(
            heading='Queue Not Empty',
            body=f'The play queue is not empty, playing "{name}" will clear it.',
            transient_for=Gio.Application.get_default().props.active_window,
        )
        self.cancellable = Gio.Cancellable()

        dialog.add_response('cancel', 'Cancel')
        dialog.set_default_response('cancel')
        dialog.add_response('append', 'Add at End')
        dialog.add_response('accept', 'Clear Queue and Play')
        dialog.set_response_appearance(
            'accept', Adw.ResponseAppearance.DESTRUCTIVE
        )
        dialog.set_response_appearance(
            'append', Adw.ResponseAppearance.SUGGESTED
        )
        dialog.choose(self.cancellable, self._on_dialog_response, album)

    def _on_dialog_response(self, dialog, response, album):
        result = dialog.choose_finish(response)
        if result == 'accept':
            self._play_album(album)
        elif result == 'append':
            self.play_queue.add_album(album)
            self.send_toast('Queue Updated')

    def _play_album(self, album):
        self.play_queue.clear()
        self.play_queue.add_album(album)
        self.player.play()

    def _on_stream_start(self, _):
        self.player_controls.set_current_track(
            self.play_queue.get_current_track()
        )

    def _on_player_state_changed(self, _, state):
        if state == 'playing':
            self._set_controls_active(True, playing=True)
        elif state in ['paused', 'ready']:
            self._set_controls_active(True, playing=False)
        elif state == 'stopped':
            self._set_controls_stopped()

    def _set_controls_stopped(self):
        if self.clear_queue:
            self._set_controls_active(False)
            self.play_queue.clear()
            self.queue_panel_split_view.set_show_sidebar(False)
        elif not self.play_queue.empty():
            self.play_queue.restart()
            self.player.ready()
        self.player_controls.deactivate()

    def _set_controls_active(self, active, playing=False):
        self.toolbar_view.set_reveal_bottom_bars(active)
        self.queue_toggle.set_sensitive(active)
        self.return_to_album.set_sensitive(active)
        self.player_controls.activate(active and playing)
