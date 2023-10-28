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

from gi.repository import Adw, Gtk, GLib, Gst, Gio, GObject
import gi
from .library import AlbumItem, TrackItem
from .album_view import AlbumView
from .player_controls import RecordBoxPlayerControls
from .player import Player
from .monitor import ProgressMonitor
from .play_queue import PlayQueue

gi.require_version('Gtk', '4.0')
gi.require_version('Gst', '1.0')


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/main_view.ui')
class MainView(Adw.Bin):
    __gtype_name__ = 'MainView'

    album_overview = Gtk.Template.Child()

    toolbar_view = Gtk.Template.Child()

    content_page = Gtk.Template.Child()

    queue_panel_split_view = Gtk.Template.Child()
    play_queue = Gtk.Template.Child()

    player_controls = Gtk.Template.Child()

    toast = Gtk.Template.Child()

    confirm_play = GObject.Property(type=bool, default=True)
    clear_queue = GObject.Property(type=bool, default=False)
    album_changed = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    show_queue = GObject.Property(type=bool, default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.player = Player(self.play_queue)
        self.player_controls.attach_to_player(self.player)

        self._setup_actions()

        self.play_queue.connect(
            'jump-to-track',
            self.player.jump_to_track,
        )
        self.player.connect(
            'player-error',
            lambda _, err: self.send_toast(f'Playback Error: {err}'),
        )

    def update_album(self, album: AlbumItem):
        self.content_page.set_title(album.raw_name)
        self.album_overview.update_album(album)

    def send_toast(self, title: str, timeout=2):
        toast = Adw.Toast()
        toast.set_title(title)
        toast.set_timeout(timeout)
        self.toast.add_toast(toast)

    def play_album(self, *_):
        if album := self.album_overview.current_album:
            self._confirm_album_play(None, album)

    def queue_add(self, *_):
        if album := self.album_overview.current_album:
            self.play_queue.add_album(album)
            if self.player.state == 'stopped':
                self.player.ready()
            self.send_toast('Queue Updated')

    def replace_queue(self, *_):
        if self.album_overview.current_album:
            self.play_queue.clear()
            self.queue_add()

    def _setup_actions(self):
        self.play_queue.connect(
            'jump-to-track',
            self.player.jump_to_track,
        )

        self.player.connect('state-changed', self._on_player_state_changed)
        self.player.connect('eos', self._on_player_eos)

    @Gtk.Template.Callback()
    def _confirm_album_play(self, _, album: AlbumItem):
        if self.player.state == 'stopped' or not self.confirm_play:
            self._play_album(album)
            return
        dialog = self._play_dialog(album.raw_name)
        dialog.choose(self.cancellable, self._on_dialog_response, album)

    @Gtk.Template.Callback()
    def _confirm_track_play(self, _, track: TrackItem):
        if self.player.state == 'stopped' or not self.confirm_play:
            self._play_track(track)
            return
        dialog = self._play_dialog(track.title)
        dialog.choose(self.cancellable, self._on_dialog_track_response, track)

    @Gtk.Template.Callback()
    def _on_add_track(self, _, track: TrackItem):
        self.play_queue.add_track(track)
        if self.player.state == 'stopped':
            self.player.ready()
        self.send_toast('Queue Updated')

    def return_to_playing(self, *_):
        if current_track := self.player.current_track:
            current_album = current_track.album
            self.emit('album_changed', current_album)

    @Gtk.Template.Callback()
    def _exit_player(self, _):
        self.player.exit()
        self._set_controls_visible(False)
        self.play_queue.clear()
        self.queue_panel_split_view.set_show_sidebar(False)

    def _play_dialog(self, name: str) -> Adw.MessageDialog:
        dialog = Adw.MessageDialog(
            heading='Already Playing',
            body=f'A song is already playing. Do you want to clear the queue and play {name}?',
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
        return dialog

    def _on_dialog_response(
        self, dialog: Adw.MessageDialog, response, album: AlbumItem
    ):
        result = dialog.choose_finish(response)
        if result == 'accept':
            self._play_album(album)
        elif result == 'append':
            self.play_queue.add_album(album)
            self.send_toast('Queue Updated')

    def _on_dialog_track_response(self, dialog, response, track):
        result = dialog.choose_finish(response)
        if result == 'accept':
            self._play_track(track)
        elif result == 'append':
            self.play_queue.add_track(track)
            self.send_toast('Queue Updated')

    def _play_album(self, album: AlbumItem):
        self.play_queue.clear()
        self.play_queue.add_album(album)
        self.player.play()

    def _play_track(self, track: TrackItem):
        self.play_queue.clear()
        self.play_queue.add_track(track)
        self.player.play()

    def _on_player_state_changed(self, _, state: str):
        if state in {'playing', 'paused'}:
            GLib.idle_add(self._set_controls_visible, True)

    def _on_player_eos(self, _):
        if self.clear_queue:
            GLib.idle_add(self._exit_player, None)

    def _set_controls_visible(self, visible: bool):
        self.toolbar_view.set_reveal_bottom_bars(visible)
