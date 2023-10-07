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

from gi.repository import Adw, Gtk, GLib, Gst, Gio, GObject
import gi
from .musicdb import MusicDB, Album
from .album_view import RecordBoxAlbumView
from .player import Player

import threading
import time

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = Player(self.play_queue)
        self.monitor_thread_id = 0
        self._setup_actions()
        self._set_controls_stopped()

    @GObject.Property(type=bool, default=False)
    def clear_queue(self):
        return self._clear_queue

    @clear_queue.setter
    def set_clear_queue(self, value):
        self._clear_queue = value

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
        self.queue_add.connect('clicked', self._on_queue_add_clicked)
        self.queue_toggle.connect('clicked', self._on_queue_toggle_clicked)

        self.play.connect('clicked', self._on_play_clicked)
        self.play_pause.connect('clicked', self._on_play_pause)
        self.skip_forward.connect('clicked', self._skip_forward)
        self.skip_backward.connect('clicked', self._skip_backward)
        self.stop.connect('clicked', self._on_stop_clicked)

        self.progress.connect('change-value', self._on_seek)

        self.player.bus.connect('message', self._on_message)
        self.player.connect('state-changed', self._on_player_state_changed)

    def _on_play_clicked(self, _):
        if album := self.album_overview.current_album:
            self.play_queue.clear()
            self.play_queue.add_album(album)
            self.player.play()
            self._start_monitor_thread()

    def _on_queue_add_clicked(self, _):
        if album := self.album_overview.current_album:
            self.play_queue.add_album(album)
            if self.player.state == 'stopped':
                self.player.ready()
            self.send_toast('Queue Updated')

    def _on_queue_toggle_clicked(self, _):
        self.queue_panel_split_view.set_show_sidebar(
            not self.queue_panel_split_view.get_show_sidebar()
        )

    def _on_play_pause(self, _):
        if self.player.state == 'ready' and self.play_queue.current_track:
            self._start_monitor_thread()
        self.player.toggle()

    def _on_stop_clicked(self, _):
        self.player.stop()

    def _on_player_state_changed(self, _, state):
        if state == 'playing':
            self._set_controls_active(playing=True)
        elif state in ['paused', 'ready']:
            self._set_controls_active(playing=False)
        elif state == 'stopped':
            self._set_controls_stopped()

    def _set_controls_stopped(self):
        self.play_pause.set_icon_name('media-playback-start-symbolic')
        self.progress.set_sensitive(False)
        if self.clear_queue:
            self.toolbar_view.set_reveal_bottom_bars(False)
            self.queue_toggle.set_sensitive(False)
            self.play_queue.clear()
        elif not self.play_queue.empty():
            self.play_queue.restart()
            self.player.ready()

    def _set_controls_active(self, playing=False):
        self.toolbar_view.set_reveal_bottom_bars(True)
        self.queue_toggle.set_sensitive(True)
        if playing:
            self.progress.set_sensitive(True)
            self.play_pause.set_icon_name('media-playback-pause-symbolic')
        else:
            self.play_pause.set_icon_name('media-playback-start-symbolic')

    def _start_monitor_thread(self):
        self.monitor_thread_id += 1
        progress_thread = threading.Thread(
            target=self._monitor_progress,
            daemon=True,
            args=(self.monitor_thread_id,),
        )
        progress_thread.daemon = True
        progress_thread.start()

    def _monitor_progress(self, num):
        while self.player.state != 'stopped' and self.monitor_thread_id == num:
            duration = self.player.get_duration() / 1000000000
            progress = self.player.get_progress() / 1000000000
            time_str = f'{int(progress // 60):02}:{int(progress % 60):02}'
            duration_str = f'{int(duration // 60):02}:{int(duration % 60):02}'
            if progress < duration:
                self.progress.set_range(0, duration)
            self.start_label.set_text(time_str)
            self.end_label.set_text(duration_str)
            GLib.idle_add(self.progress.set_value, progress)
            time.sleep(0.5)
        self.start_label.set_text('')
        self.end_label.set_text('')

    def _on_message(self, _, message):
        if message.type == Gst.MessageType.STREAM_START:
            if current_track := self.play_queue.get_current_track():
                self.playing_song.set_markup(
                    f'<span size="large">{GLib.markup_escape_text(current_track.title)}</span>'
                )
                self.playing_artist.set_markup(
                    f'<span size="small">{GLib.markup_escape_text(current_track.album.artist)}</span>'
                )
            else:
                self.playing_song.set_text('')
                self.playing_artist.set_text('')

        if message.type == Gst.MessageType.EOS:
            self._set_controls_stopped()

    def _on_seek(self, _, __, value):
        self.player.seek(value * 1000000000)

    def _skip_forward(self, _):
        if self.play_queue.next():
            self.player.play()
            self.play_pause.set_icon_name('media-playback-pause-symbolic')

    def _skip_backward(self, _):
        if self.play_queue.previous():
            self.player.play()
            self.play_pause.set_icon_name('media-playback-pause-symbolic')
