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

from gi.repository import Adw, Gtk, GLib, Gio, GObject
import gi
from .library import MusicLibrary
from .library_lists import AlbumItem, ArtistItem, ArtistList, AlbumList
from .musicdb import MusicDB
from .parser import MusicParser
from .play_queue import PlayQueue
from .player import Player
from .main_view import MainView

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/window.ui')
class RecordBoxWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'RecordBoxWindow'

    # outer_split is the AdwOverlaySplitView with the artist/album lists as it's sidebar
    outer_split = Gtk.Template.Child()

    library = Gtk.Template.Child()

    main_page = Gtk.Template.Child()
    main_view = Gtk.Template.Child()

    play_button = Gtk.Template.Child()

    lists_toggle = Gtk.Template.Child()
    queue_toggle = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = kwargs.get('application', None)

        self.parser = MusicParser()

        if self.app.settings.get_boolean('restore-window-state'):
            self._bind_state()
        self._bind_settings()
        self._setup_actions()

        if self.app.settings.get_boolean('sync-on-startup'):
            self.library.sync_library(None)

    def _bind_state(self):
        self._bind('width', self, 'default-width')
        self._bind('height', self, 'default-height')
        self._bind('is-maximized', self, 'maximized')
        self._bind('is-fullscreen', self, 'fullscreened')

    def _bind_settings(self):
        self._set('artist-sort', self.library, 'artist-sort')
        self._set('album-sort', self.library, 'album-sort')

        self._bind('clear-queue', self.main_view, 'clear_queue')
        self._bind(
            'expand-discs', self.main_view.album_overview, 'expand_discs'
        )

        self._bind('confirm-play', self.main_view, 'confirm_play')

        self._bind('show-all-artists', self.library, 'show_all_artists')

    def _bind(self, key: str, obj: GObject.Object, property: str):
        self.app.settings.bind(
            key, obj, property, Gio.SettingsBindFlags.DEFAULT
        )

    def _set(self, key: str, obj: GObject.Object, property: str):
        obj.set_property(property, self.app.settings.get_value(key).unpack())

    def _setup_actions(self):
        self.play_action = self._create_action(
            'play-album', self.main_view.play_album
        )
        self.queue_add = self._create_action(
            'add-album', self.main_view.append_queue
        )
        self.replace_queue = self._create_action(
            'replace-queue', self.main_view.overwrite_queue
        )
        self.return_to_playing = self._create_action(
            'return-to-playing', self.main_view.return_to_playing
        )
        self.undo_queue = self._create_action(
            'undo-queue', self.main_view.undo, enabled=True
        )

        self.filter_all_albums = self._create_action(
            'filter-all', self.library.filter_all
        )
        self.library.bind_property(
            'filter-all-albums',
            self.filter_all_albums,
            'enabled',
            GObject.BindingFlags.INVERT_BOOLEAN,
        )
        self.artist_sort = Gio.PropertyAction.new(
            'artist-sort',
            self.library,
            'artist-sort',
        )
        self.add_action(self.artist_sort)

        self.album_sort = Gio.PropertyAction.new(
            'album-sort',
            self.library,
            'album-sort',
        )
        self.add_action(self.album_sort)

        self.main_view.player.connect(
            'state-changed',
            self._on_player_state_changed,
        )

        self.main_view.player_controls.connect(
            'exit-player',
            self._exit_player,
        )

    def _create_action(self, name, callback, enabled=False):
        action = Gio.SimpleAction.new(name, None)
        action.connect('activate', callback)
        action.set_enabled(enabled)
        self.add_action(action)
        return action

    @Gtk.Template.Callback()
    def _album_selected(self, _, album: AlbumItem):
        self.main_view.update_album(album)
        self.main_page.set_title(album.raw_name)
        self.outer_split.set_show_sidebar(
            self.outer_split.get_collapsed() == False
        )

        self.play_button.set_sensitive(True)
        self.play_action.set_enabled(True)
        self.queue_add.set_enabled(True)

    @Gtk.Template.Callback()
    def _close_sidebar(self, _):
        self.outer_split.set_show_sidebar(False)

    @Gtk.Template.Callback()
    def _on_album_changed(self, _, album_name: str):
        album = self.library.find_album(album_name)
        self.library.select_album(album)

        self.main_page.set_title(album.raw_name)
        self.main_view.update_album(album)

    @Gtk.Template.Callback()
    def _on_album_activated(self, *_):
        # album row activation only happens on double-click, and the row
        # gets selected on the first click, setting the main_view's album,
        # so we can just call the play_album callback.
        self.main_view.play_album()

    def _on_player_state_changed(self, _, state):
        self.set_hide_on_close(
            self.app.settings.get_boolean('background-playback')
            and state in ['playing', 'paused']
        )
        if state != 'stopped':
            self.replace_queue.set_enabled(True)
            self.queue_toggle.set_sensitive(True)
            self.return_to_playing.set_enabled(True)

    def _exit_player(self, *_):
        self.return_to_playing.set_enabled(False)
        self.queue_toggle.set_sensitive(False)
        self.replace_queue.set_enabled(False)
