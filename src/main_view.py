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
from .musicdb import MusicDB, Album
from .album_view import RecordBoxAlbumView
from .player import Player
from .monitor import ProgressMonitor

gi.require_version('Gtk', '4.0')
gi.require_version('Gst', '1.0')


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/main_view.ui')
class MainView(Adw.Bin):
    __gtype_name__ = 'MainView'

    album_overview = Gtk.Template.Child()

    toolbar_view = Gtk.Template.Child()

    queue_toggle = Gtk.Template.Child()
    queue_panel_split_view = Gtk.Template.Child()
    queue_add = Gtk.Template.Child()
    play_queue = Gtk.Template.Child()

    return_to_album = Gtk.Template.Child()

    lists_toggle = Gtk.Template.Child()

    player_controls = Gtk.Template.Child()
    play = Gtk.Template.Child()
    play_pause = Gtk.Template.Child()
    skip_forward = Gtk.Template.Child()
    skip_backward = Gtk.Template.Child()

    stop = Gtk.Template.Child()
    loop = Gtk.Template.Child()

    playing_song = Gtk.Template.Child()
    playing_artist = Gtk.Template.Child()

    progress = Gtk.Template.Child()
    start_label = Gtk.Template.Child()
    end_label = Gtk.Template.Child()

    toast = Gtk.Template.Child()

    _clear_queue = False
    _confirm_play = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = Player(self.play_queue)
        self.monitor = ProgressMonitor(
            self.player, self.progress, self.start_label, self.end_label
        )
        self.monitor_thread_id = 0
        self._setup_actions()
        self._set_controls_stopped()

    @GObject.Signal(
        arg_types=(GObject.TYPE_PYOBJECT,), return_type=GObject.TYPE_NONE
    )
    def album_changed(self, album):
        self.update_album(album)

    @GObject.Property(type=bool, default=False)
    def clear_queue(self):
        return self._clear_queue

    @clear_queue.setter
    def set_clear_queue(self, value):
        self._clear_queue = value

    @GObject.Property(type=bool, default=True)
    def confirm_play(self):
        return self._confirm_play

    @confirm_play.setter
    def set_confirm_play(self, value):
        self._confirm_play = value

    def set_breakpoint(self, _, breakpoint_num):
        self.album_overview.set_breakpoint(None)
        if breakpoint_num > 2:
            self.lists_toggle.set_visible(True)

    def unset_breakpoint(self, _, breakpoint_num):
        self.album_overview.unset_breakpoint(None)
        if breakpoint_num > 2:
            self.lists_toggle.set_visible(False)

    def update_album(self, album: Album):
        self.album_overview.update_album(album)
        self.play.set_sensitive(True)
        self.queue_add.set_sensitive(True)

    def send_toast(self, title, timeout=2):
        toast = Adw.Toast()
        toast.set_title(title)
        toast.set_timeout(timeout)
        self.toast.add_toast(toast)

    def _setup_actions(self):
        self.play.connect('clicked', self._on_play_clicked)
        self.queue_add.connect('clicked', self._on_queue_add)

        self.play_pause.connect('clicked', self._on_play_pause)
        self.skip_forward.connect('clicked', self._skip_forward)
        self.skip_backward.connect('clicked', self._skip_backward)

        self.stop.connect('clicked', self._on_stop_clicked)

        self.return_to_album.connect('clicked', self._on_return_to_album)
        self.queue_toggle.connect('clicked', self._on_queue_toggle)

        self.progress.connect('change-value', self.monitor.seek_event)

        self.player.bus.connect('message', self._on_message)
        self.player.connect('state-changed', self._on_player_state_changed)

        self.album_overview.connect('play_track', self._on_play_track)
        self.album_overview.connect('add_track', self._on_add_track)

    def _on_play_clicked(self, _):
        if not (album := self.album_overview.current_album):
            return
        if self.player.state == 'stopped' or not self.confirm_play:
            self._play_album(album)
        else:
            self._confirm_album_play(album, album.name)

    def _confirm_album_play(self, album, name):
        dialog = Adw.MessageDialog(
            heading='Queue Not Empty',
            body=f'The play queue is not empty, playing "{name}" will clear it.',
            transient_for=Gio.Application.get_default().props.active_window,
        )
        self.cancellable = Gio.Cancellable()

        # dialog.set_body_use_markup(True)
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
        self.monitor.start_thread()

    def _on_queue_add(self, _):
        if album := self.album_overview.current_album:
            self.play_queue.add_album(album)
            if self.player.state == 'stopped':
                self.player.ready()
            self.send_toast('Queue Updated')

    def _on_queue_toggle(self, _):
        self.queue_panel_split_view.set_show_sidebar(
            not self.queue_panel_split_view.get_show_sidebar()
        )

    def _on_return_to_album(self, _):
        if self.play_queue.current_track:
            current_album = self.play_queue.get_current_track().album
            self.emit('album_changed', current_album)

    def _on_play_pause(self, _):
        if self.player.state == 'ready' and self.play_queue.current_track:
            self.monitor.start_thread()
        self.player.toggle()

    def _on_stop_clicked(self, _):
        self.player.stop()

    def _on_player_state_changed(self, _, state):
        if state == 'playing':
            self._set_controls_ready(playing=True)
        elif state in ['paused', 'ready']:
            self._set_controls_ready(playing=False)
        elif state == 'stopped':
            self._set_controls_stopped()
            self.monitor.stop_thread()

    def _set_controls_stopped(self):
        self.play_pause.set_icon_name('media-playback-start-symbolic')
        self.progress.set_sensitive(False)
        if self.clear_queue:
            self._set_controls_active(False)
            self.play_queue.clear()
            self.queue_panel_split_view.set_show_sidebar(False)
        elif not self.play_queue.empty():
            self.play_queue.restart()
            self.player.ready()

    def _set_controls_ready(self, playing=False):
        self._set_controls_active(True)
        if playing:
            self.progress.set_sensitive(True)
            self.play_pause.set_icon_name('media-playback-pause-symbolic')
        else:
            self.play_pause.set_icon_name('media-playback-start-symbolic')

    def _set_controls_active(self, active):
        self.toolbar_view.set_reveal_bottom_bars(active)
        self.queue_toggle.set_sensitive(active)
        self.return_to_album.set_sensitive(active)

    def _on_message(self, _, message):
        if message.type == Gst.MessageType.STREAM_START:
            if current_track := self.play_queue.get_current_track():
                self.playing_song.set_markup(
                    f'<span size="large">{GLib.markup_escape_text(current_track.title)}</span>'
                )
                artists = map(GLib.markup_escape_text, current_track.artists)
                self.playing_artist.set_markup(
                    f'<span size="small">{", ".join(artists)}</span>'
                )
                self.end_label.set_text(current_track.length_str())
            else:
                self.playing_song.set_text('')
                self.playing_artist.set_text('')
                self.end_label.set_text('0:00')

        if message.type == Gst.MessageType.EOS:
            self._set_controls_stopped()
            self.monitor.stop_thread()

    def _skip_forward(self, _):
        if self.play_queue.next():
            self.player.play()
            self.play_pause.set_icon_name('media-playback-pause-symbolic')

    def _skip_backward(self, _):
        if self.play_queue.previous():
            self.player.play()
            self.play_pause.set_icon_name('media-playback-pause-symbolic')

    def _on_play_track(self, _, track):
        album = self._get_album_from_track(track)
        if self.player.state == 'stopped' or not self.confirm_play:
            self._play_album(album)
        else:
            self._confirm_album_play(album, track.title)

    def _on_add_track(self, _, track):
        album = self._get_album_from_track(track)
        self.play_queue.add_album(album)
        if self.play_queue.empty():
            self.player.ready()
        self.send_toast('Queue Updated')

    def _get_album_from_track(self, track):
        result = copy(track.album)
        result.tracks = [track]
        result.artists = track.artists
        return result
