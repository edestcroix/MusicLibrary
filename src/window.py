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
import json
import os
from .library import MusicLibrary
from .items import TrackItem, AlbumItem
from .library_lists import ArtistList, AlbumList
from .musicdb import MusicDB
from .parser import MusicParser
from .play_queue import PlayQueue
from .player import PlayerState, Player
from .album_view import AlbumView
from .player_controls import RecordBoxPlayerControls

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

TrackList = list[TrackItem]


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/window.ui')
class RecordBoxWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'RecordBoxWindow'

    library_split = Gtk.Template.Child()
    queue_panel_split_view = Gtk.Template.Child()

    # Major UI components
    library = Gtk.Template.Child()
    album_overview = Gtk.Template.Child()
    player_controls = Gtk.Template.Child()
    play_queue = Gtk.Template.Child()

    # the AdwNavigationPage in the content part of the library_split
    main_page = Gtk.Template.Child()

    toolbar_view = Gtk.Template.Child()

    play_button = Gtk.Template.Child()
    queue_toggle = Gtk.Template.Child()

    toast_overlay = Gtk.Template.Child()

    player_active = GObject.Property(type=bool, default=False)

    _last_toast = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = kwargs.get('application', None)

        if self.app.settings.get_boolean('restore-window-state'):
            self._bind('width', self, 'default-width')
            self._bind('height', self, 'default-height')
            self._bind('is-maximized', self, 'maximized')
            self._bind('is-fullscreen', self, 'fullscreened')

        self._bind('music-directory', self.library, 'music_directory')
        self._set('artist-sort', self.library, 'artist-sort')
        self._set('album-sort', self.library, 'album-sort')
        self._bind('show-all-artists', self.library, 'show_all_artists')

        self._bind('expand-discs', self.album_overview, 'expand_discs')

        if self.app.settings.get_boolean('sync-on-startup'):
            self.library.sync_library(None, show_spinner=False)
        else:
            self.library.present()

        self._setup_actions()

    def attach_to_player(self, player: Player):
        self.player = player
        self.player.attach_to_play_queue(self.play_queue)
        self.player_controls.attach_to_player(self.player)

        self.player.connect(
            'player-error',
            lambda _, err: self.send_toast(f'Playback Error: {err}'),
        )
        self.player.connect('state-changed', self._on_player_state_changed)
        self.player.connect('eos', self._on_player_eos)

        self._bind('rg-mode', self.player, 'rg-mode')
        self._bind('rg-enabled', self.player, 'rg-enabled')
        self._bind('rg-preamp', self.player, 'rg-preamp')
        self._bind('rg-fallback', self.player, 'rg-fallback')

        loop = Gio.PropertyAction.new(
            'loop',
            self.player,
            'loop',
        )
        stop_after_current = Gio.PropertyAction.new(
            'stop_after_current',
            self.player,
            'stop-after-current',
        )
        self.add_action(stop_after_current)
        self.add_action(loop)
        self.stop_player = self._create_action(
            'stop', lambda *_: self.player.stop()
        )
        if self.app.settings.get_boolean('restore-playback-state'):
            self.restore_state()

    def send_toast(self, title: str, button: str = '', action: str = ''):
        toast = Adw.Toast(title=title, timeout=3)
        if button:
            toast.set_button_label(button)
        if action:
            toast.set_action_name(action)
        if self._last_toast:
            self._last_toast.dismiss()

        self.toast_overlay.add_toast(toast)
        self._last_toast = toast

    ### Action Callbacks ###

    @Gtk.Template.Callback()
    def play(self, _, index: GLib.Variant = None, disc: GLib.Variant = None):
        """Callback for various play actions. If index is provided, it will begin playing
        the current album at the given index. If disc is provided, it will play the tracks
        from the current album with said disc number. If neither are provided, it will
        play the entire album."""
        if album := self.album_overview.current_album:
            if disc and (d := disc.get_int32()):
                album = self._album_to_disc(album, d)
            self._play_album(album, index.get_int32() if index else 0)

    def play_single(self, _, index: GLib.Variant):
        """Plays the track at the given index in the current album.
        Callback for the play-single action. Unlike play, only the track at the given
        index will be added to the queue, rather than the entire album."""
        if album := self.album_overview.current_album:
            i = index.get_int32()
            self._play_tracks(album.tracks[i : i + 1])

    def append(self, _, index: GLib.Variant, disc: GLib.Variant = None):
        """Gets the track at the given index in the current album and adds
        it to the queue. Callback for the append action. If a disc number is
        provided, it will instead add that disc's tracks to the queue."""
        tracks = self._current_album_tracks()

        if (i := index.get_int32()) == -1:
            album = self.album_overview.current_album
            if disc and (d := disc.get_int32()):
                album = self._album_to_disc(album, d)
            self._add_album_to_queue(album)
        else:
            self._add_to_queue(tracks[i : i + 1])

    def insert(self, _, index: GLib.Variant):
        tracks = self._current_album_tracks()
        self.play_queue.insert(tracks[index.get_int32()])

    def overwrite_queue(self, _, disc: GLib.Variant = None):
        album = self.album_overview.current_album
        if disc and (d := disc.get_int32()):
            album = self._album_to_disc(album, d)
        self._add_album_to_queue(album, overwrite=True)

    def undo(self, *_):
        self.play_queue.undo()

    def return_to_playing(self, *_):
        if current_track := self.player.current_track:
            album = self.library.find_album_by_track(current_track)
            self.library.select_album(current_track.albumartist, album)
            if self.album_overview.current_album != album:
                self._update_album(album)

    def save_state(self):
        data = self.play_queue.export()
        data['current']['position'] = self.player.position
        if current_album := self.album_overview.current_album:
            data['current-album'] = {
                'albumartist': current_album.albumartist,
                'title': current_album.title,
            }
        with open(
            f'{GLib.get_user_data_dir()}/RecordBox/state.json', 'w'
        ) as f:
            f.write(json.dumps(data))

    def restore_state(self):
        if not os.path.exists(
            state_file := f'{GLib.get_user_data_dir()}/RecordBox/state.json'
        ):
            return
        with open(state_file, 'r') as f:
            state_data = json.loads(f.read())
            if not state_data['queue']:
                return
            self.play_queue.import_state(state_data)
            self.player.resume(state_data['current']['position'])

        self.return_to_playing()
        if current_album := self.album_overview.current_album:
            # the selected items in the lists get cleared for some reason while
            # the window is opening, so we need to reselect them after a delay
            GLib.timeout_add(
                300,
                self.library.select_album,
                current_album.albumartist,
                current_album,
            )

    ## UI Callbacks ##

    @Gtk.Template.Callback()
    def _album_changed(self, _, album: AlbumItem):
        self._update_album(album)
        self.play_action.set_enabled(True)
        self.play_button.set_sensitive(True)
        self.add_album.set_enabled(True)

    @Gtk.Template.Callback()
    def _album_confirmed(self, *_):
        self.library_split.set_show_sidebar(
            self.library_split.get_collapsed() == False
        )

    @Gtk.Template.Callback()
    def _close_sidebar(self, _):
        self.library_split.set_show_sidebar(False)

    ## Private methods ##

    # library and queue methods #

    def _play_tracks(self, tracks: list[TrackItem], start_index: int = 0):
        self.play_queue.overwrite_w_tracks(tracks, start_index)
        self.play_queue.remove_backups()
        self.player.play()

    def _play_album(self, album: AlbumItem, start_index: int = 0):
        self.play_queue.overwrite_w_album(album, start_index)
        self.play_queue.remove_backups()
        self.play_queue.set_index(start_index)
        self.player.play()

    def _current_album_tracks(self) -> TrackList:
        if current_album := self.album_overview.current_album:
            return current_album.tracks
        else:
            return []

    def _add_album_to_queue(
        self, album: AlbumItem, overwrite=False, toast=True
    ):
        if overwrite:
            self.play_queue.overwrite_w_album(album)
            toast_msg = 'Queue Replaced'
        else:
            self.play_queue.append_album(album)
            if self.player.state == PlayerState.STOPPED:
                self.player.ready()
            toast_msg = 'Queue Updated'
        if toast and not self.queue_toggle.get_active():
            self.send_toast(toast_msg, 'Show Queue', 'win.open-queue')

    def _add_to_queue(self, tracks: TrackList, toast=True):
        self.play_queue.append(tracks)
        if self.player.state == PlayerState.STOPPED:
            self.player.ready()
        if toast and not self.queue_toggle.get_active():
            self.send_toast('Queue Updated', 'Show Queue', 'win.open-queue')

    def _update_album(self, album: AlbumItem):
        self.main_page.set_title(album.title)
        self.album_overview.update_album(album)

    def _album_to_disc(self, album: AlbumItem, disc_number: int) -> AlbumItem:
        tracks = [t for t in album.tracks if t.discnumber == disc_number]
        album = album.clone()
        album.tracks = tracks
        album.length = sum(t.length for t in tracks)
        if discsub := album.tracks[0].discsubtitle:
            album.title += f' ({discsub})'
        else:
            album.title += f' (Disc {disc_number})'

        return album

    # player specific methods #

    def _on_player_state_changed(self, _, state):
        if state != PlayerState.STOPPED:
            self.player_active = True
            self.set_hide_on_close(
                self.app.settings.get_boolean('background-playback')
            )
        else:
            self.set_hide_on_close(False)

    def _on_player_eos(self, _):
        if self.app.settings.get_boolean('clear-queue'):
            self._exit_player(None)

    def _exit_player(self, *_):
        self.player.exit()
        self.player_active = False
        self.play_queue.clear()

    # action and settings setup/binding #

    def _bind(self, key: str, obj: GObject.Object, property: str):
        self.app.settings.bind(
            key, obj, property, Gio.SettingsBindFlags.DEFAULT
        )

    def _set(self, key: str, obj: GObject.Object, property: str):
        obj.set_property(property, self.app.settings.get_value(key).unpack())

    def _setup_actions(self):
        self.play_action = self._create_action(
            'play',
            self.play,
            parameter_type=GLib.VariantType('i'),
        )
        self._create_action(
            'play-single',
            self.play_single,
            parameter_type=GLib.VariantType('i'),
        )
        self._create_action(
            'play-disc',
            lambda _, disc: self.play(None, 0, disc=disc),
            parameter_type=GLib.VariantType('i'),
        )

        self.add_album = self._create_action(
            'add-album',
            lambda *_: self.append(None, GLib.Variant('i', -1)),
            enabled=False,
        )
        self._create_action(
            'append',
            self.append,
            parameter_type=GLib.VariantType('i'),
        )
        self._create_action(
            'append-disc',
            lambda _, disc: self.append(
                None, GLib.Variant('i', -1), disc=disc
            ),
            parameter_type=GLib.VariantType('i'),
        )

        insert = self._create_action(
            'insert',
            self.insert,
            enabled=False,
            parameter_type=GLib.VariantType('i'),
        )
        self.play_queue.bind_property(
            'empty', insert, 'enabled', GObject.BindingFlags.INVERT_BOOLEAN
        )

        replace_queue = self._create_action(
            'replace-queue', self.overwrite_queue, enabled=False
        )
        self.play_queue.bind_property(
            'empty',
            replace_queue,
            'enabled',
            GObject.BindingFlags.INVERT_BOOLEAN,
        )
        self._create_action(
            'replace-disc',
            self.overwrite_queue,
            parameter_type=GLib.VariantType('i'),
        )
        return_to_playing = self._create_action(
            'return-to-playing', self.return_to_playing, enabled=False
        )
        self.bind_property(
            'player_active',
            return_to_playing,
            'enabled',
            GObject.BindingFlags.DEFAULT,
        )
        self._create_action('exit_player', self._exit_player)

        self._create_action('undo-queue', lambda *_: self.play_queue.undo())
        self._create_action('redo-queue', lambda *_: self.play_queue.redo())

        self._create_action(
            'open-queue', lambda *_: self.queue_toggle.set_active(True)
        )

        filter_all_albums = self._create_action(
            'filter-all', self.library.filter_all, enabled=False
        )
        self.library.bind_property(
            'filter-all-albums',
            filter_all_albums,
            'enabled',
            GObject.BindingFlags.INVERT_BOOLEAN,
        )
        self.add_action(
            Gio.PropertyAction.new(
                'artist-sort',
                self.library,
                'artist-sort',
            )
        )
        self.add_action(
            Gio.PropertyAction.new(
                'album-sort',
                self.library,
                'album-sort',
            )
        )

    def _create_action(
        self, name, callback, enabled=True, parameter_type=None
    ):
        action = Gio.SimpleAction.new(name, parameter_type)
        action.connect('activate', callback)
        action.set_enabled(enabled)
        self.add_action(action)
        return action
