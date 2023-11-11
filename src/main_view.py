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
from .library_lists import AlbumItem, TrackItem
from .album_view import AlbumView, PlayRequest
from .player_controls import RecordBoxPlayerControls
from .player import Player
from .monitor import ProgressMonitor
from .play_queue import PlayQueue

from collections import deque

gi.require_version('Gtk', '4.0')
gi.require_version('Gst', '1.0')

TrackList = list[TrackItem]


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/main_view.ui')
class MainView(Adw.Bin):
    """The main view is the widget container that handles the album overview, play queue, and player controls,
    coordinating communication between them. It's also currently where the player itself is created, although this
    might get moved to the application class in the future."""

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
    show_queue = GObject.Property(type=bool, default=False)

    album_changed = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    undo_toasts = deque(maxlen=10)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.player = Player(self.play_queue)
        self.player_controls.attach_to_player(self.player)

        self.player.connect(
            'player-error',
            lambda _, err: self.send_toast(f'Playback Error: {err}'),
        )
        self.player.connect('state-changed', self._on_player_state_changed)
        self.player.connect('eos', self._on_player_eos)

    def update_album(self, album: AlbumItem):
        self.content_page.set_title(album.raw_name)
        self.album_overview.update_album(album)

    def send_toast(
        self,
        title: str,
        timeout=2,
        undo=False,
        priority=Adw.ToastPriority.HIGH,
    ):
        toast = Adw.Toast(title=title, priority=priority)
        toast.set_timeout(max(timeout, 3) if undo else timeout)
        if undo:
            toast.set_button_label('Undo')
            toast.set_action_name('win.undo-queue')
            self.undo_toasts.append(toast)
        self.toast.add_toast(toast)

    ### Callbacks for the album action menu ###

    def play_album(self, *_):
        if album := self.album_overview.current_album:
            self._confirm_play(PlayRequest(album.tracks, 0), album.raw_name)

    def append_queue(self, *_):
        self._add_to_queue(self._current_album_tracks())

    def overwrite_queue(self, *_):
        self._add_to_queue(self._current_album_tracks(), overwrite=True)

    ## Misc callbacks ##

    def undo(self, *_):
        if self.undo_toasts:
            self.undo_toasts.pop().dismiss()
        self.play_queue.undo()

    def return_to_playing(self, *_):
        if current_track := self.player.current_track:
            current_album = current_track.album
            self.emit('album_changed', current_album)

    ## UI Callbacks ##

    @Gtk.Template.Callback()
    def _on_play_request(self, _, play_request: PlayRequest):
        tracks, track_index = play_request
        self._confirm_play(play_request, tracks[track_index].title)

    @Gtk.Template.Callback()
    def _on_add_track(self, _, track: TrackItem):
        self._add_to_queue([track])

    @Gtk.Template.Callback()
    def _on_add_track_next(self, _, track: TrackItem):
        was_empty = self.play_queue.is_empty()
        self.play_queue.add_after_current(track)
        if self.player.state == 'stopped':
            self.player.ready()
        self.send_toast('Track Inserted', undo=not was_empty)

    @Gtk.Template.Callback()
    def _exit_player(self, _):
        self.player.exit()
        self._set_controls_visible(False)
        self.play_queue.clear()
        self.queue_panel_split_view.set_show_sidebar(False)

    ## Private methods ##

    def _confirm_play(self, play_request: PlayRequest, name: str):
        if self.player.state == 'stopped' or not self.confirm_play:
            self._play_tracks(play_request)
            return
        dialog = self._play_dialog(name)
        dialog.choose(self.cancellable, self._on_dialog_response, play_request)

    def _play_dialog(self, name: str) -> Adw.MessageDialog:
        dialog = Adw.MessageDialog(
            heading='Already Playing',
            body=f'A song is already playing. Do you want to clear the queue and play {name}?',
            transient_for=Gio.Application.get_default().props.active_window,
        )
        self.cancellable = Gio.Cancellable()

        dialog.add_response('cancel', 'Cancel')
        dialog.set_default_response('cancel')
        dialog.add_response('append', 'Append To Queue')
        dialog.add_response('accept', 'Clear Queue and Play')
        dialog.set_response_appearance(
            'accept', Adw.ResponseAppearance.DESTRUCTIVE
        )
        dialog.set_response_appearance(
            'append', Adw.ResponseAppearance.SUGGESTED
        )
        return dialog

    def _on_dialog_response(
        self, dialog: Adw.MessageDialog, response, play_request: PlayRequest
    ):
        result = dialog.choose_finish(response)
        if result == 'accept':
            self._play_tracks(play_request)
        elif result == 'append':
            self._add_to_queue(play_request.tracks)

    def _play_tracks(self, play_request: PlayRequest):
        self._add_to_queue(play_request.tracks, overwrite=True, toast=False)
        self.play_queue.set_index(play_request.index)
        self.play_queue.remove_backups()
        self.player.play()

    def _current_album_tracks(self) -> TrackList:
        if current_album := self.album_overview.current_album:
            return current_album.tracks
        else:
            return []

    def _add_to_queue(self, tracks: TrackList, overwrite=False, toast=True):
        was_empty = self.play_queue.is_empty()
        if overwrite:
            self.play_queue.overwrite(tracks)
        else:
            self.play_queue.append(tracks)
            if self.player.state == 'stopped':
                self.player.ready()
        if toast:
            self.send_toast('Queue Updated', undo=not was_empty)

    def _on_player_state_changed(self, _, state: str):
        if state in {'playing', 'paused'}:
            GLib.idle_add(self._set_controls_visible, True)

    def _on_player_eos(self, _):
        if self.clear_queue:
            GLib.idle_add(self._exit_player, None)

    def _set_controls_visible(self, visible: bool):
        self.toolbar_view.set_reveal_bottom_bars(visible)
