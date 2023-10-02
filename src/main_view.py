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

from gi.repository import Adw, Gtk, Gdk, GLib, Pango
import gi

gi.require_version('Gtk', '4.0')

from .musicdb import MusicDB, Album
from .album_view import MusicLibraryAlbumView
from .player import Player


@Gtk.Template(resource_path='/ca/edestcroix/MusicLibary/main_view.ui')
class MainView(Adw.Bin):
    __gtype_name__ = 'MainView'

    album_overview = Gtk.Template.Child()

    queue_toggle = Gtk.Template.Child()
    queue_panel_split_view = Gtk.Template.Child()
    queue_add = Gtk.Template.Child()
    play_queue = Gtk.Template.Child()

    lists_toggle = Gtk.Template.Child()

    play = Gtk.Template.Child()
    play_pause = Gtk.Template.Child()
    player_controls = Gtk.Template.Child()

    playing_song = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = Player(self.play_queue)
        self._setup_actions()

    def set_breakpoint(self, _, breakpoint_num):
        self.album_overview.set_breakpoint(None)
        if breakpoint_num > 1:
            self.lists_toggle.set_visible(True)

    def unset_breakpoint(self, _, breakpoint_num):
        print(breakpoint_num)
        self.album_overview.unset_breakpoint(None)
        if breakpoint_num > 1:
            self.lists_toggle.set_visible(False)

    def update_album(self, album: Album):
        self.album_overview.update_album(album)

    def _setup_actions(self):
        self.play.connect('clicked', self._on_play_clicked)
        self.queue_add.connect('clicked', self._on_queue_add_clicked)
        self.queue_toggle.connect('clicked', self._on_queue_toggle_clicked)
        self.play_pause.connect('clicked', self._on_play_pause)

    def _on_play_clicked(self, _):
        if album := self.album_overview.current_album:
            self.play_queue.clear()
            self.play_queue.add_album(album)
            self.player.play()
            self.player_controls.set_revealed(True)
            self.play_pause.set_icon_name('media-playback-pause-symbolic')

            self.playing_song.set_text(
                f'{self.play_queue.get_current_track().title} - {album.artist}'
            )

            # duration = self.player.get_duration()
            # GLib.timeout_add(duration, self._monitor_progress)

    def _on_queue_add_clicked(self, _):
        if album := self.album_overview.current_album:
            self.play_queue.add_album(album)

    def _on_queue_toggle_clicked(self, _):
        self.queue_panel_split_view.set_show_sidebar(
            not self.queue_panel_split_view.get_show_sidebar()
        )

    def _on_play_pause(self, button):
        self.player.toggle()
        button.set_icon_name(
            'media-playback-pause-symbolic'
            if self.player.state == 'playing'
            else 'media-playback-start-symbolic'
        )
