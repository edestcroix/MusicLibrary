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
from .items import TrackItem, AlbumItem, ArtistItem
from .library_lists import ArtistList, AlbumList
from .musicdb import MusicDB
from .parser import MusicParser
from .play_queue import PlayQueue
from .player import Player
from .album_view import AlbumView
from .player_controls import RecordBoxPlayerControls

from collections import deque, namedtuple

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

TrackList = list[TrackItem]
PlayRequest = namedtuple('PlayRequest', ['tracks', 'index'])


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

    undo_toasts = deque(maxlen=10)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = kwargs.get('application', None)

        if self.app.settings.get_boolean('restore-window-state'):
            self._bind('width', self, 'default-width')
            self._bind('height', self, 'default-height')
            self._bind('is-maximized', self, 'maximized')
            self._bind('is-fullscreen', self, 'fullscreened')

        if self.app.settings.get_boolean('sync-on-startup'):
            self.library.sync_library(None)

        self._set('artist-sort', self.library, 'artist-sort')
        self._set('album-sort', self.library, 'album-sort')
        self._bind('expand-discs', self.album_overview, 'expand_discs')
        self._bind('show-all-artists', self.library, 'show_all_artists')

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

    def update_album(self, album: AlbumItem):
        self.main_page.set_title(album.raw_name)
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
        self.toast_overlay.add_toast(toast)

    ### Action Callbacks ###

    def play(self, _, index: GLib.Variant):
        """Callback for the play action. Plays the currently selected album
        starting at the given index. Will destructively overwrite the queue"""
        if album := self.album_overview.current_album:
            i = index.get_int32()
            name = album.tracks[i].title if i else album.raw_name
            self._confirm_play(album.tracks, i, name)

    def append_album(self, *_):
        """Callback for the add-album action. Can't currently be combined with append
        track like how play is, because the add to queue option in the album menu
        doesn't work with the append action for some reason."""
        self._add_to_queue(self._current_album_tracks())

    def append_track(self, _, index: GLib.Variant):
        """Gets the track at the given index in the current album and adds
        it to the queue. Callback for the append action."""
        i: int = index.get_int32()
        self._add_to_queue(self._current_album_tracks()[i : i + 1])

    def overwrite_queue(self, *_):
        self._add_to_queue(self._current_album_tracks(), overwrite=True)

    def insert_track(self, _, index: GLib.Variant):
        track = self._current_album_tracks()[index.get_int32()]
        was_empty = self.play_queue.is_empty()
        self.play_queue.add_after_current(track)
        if self.player.state == 'stopped':
            self.player.ready()
        self.send_toast('Track Inserted', undo=not was_empty)

    def undo(self, *_):
        if self.undo_toasts:
            self.undo_toasts.pop().dismiss()
        self.play_queue.undo()

    def return_to_playing(self, *_):
        if current_track := self.player.current_track:
            current_album = current_track.album
            album = self.library.find_album(current_album)
            self.library.select_album(album)

            self.main_page.set_title(album.raw_name)
            self.update_album(album)

    ## UI Callbacks ##

    @Gtk.Template.Callback()
    def _play_album(self, *_):
        """Callback for when a row in the album list is activated."""
        if album := self.album_overview.current_album:
            self._confirm_play(album.tracks, 0, album.raw_name)

    @Gtk.Template.Callback()
    def _album_selected(self, _, album: AlbumItem):
        self.update_album(album)
        self.main_page.set_title(album.raw_name)
        self.library_split.set_show_sidebar(
            self.library_split.get_collapsed() == False
        )

        self.play_action.set_enabled(True)
        self.play_button.set_sensitive(True)
        self.add_album.set_enabled(True)

    @Gtk.Template.Callback()
    def _close_sidebar(self, _):
        self.library_split.set_show_sidebar(False)

    @Gtk.Template.Callback()
    def _exit_player(self, _):
        self.player.exit()
        self.toolbar_view.set_reveal_bottom_bars(False)
        self.play_queue.clear()
        self.queue_panel_split_view.set_show_sidebar(False)
        self.return_to_playing.set_enabled(False)
        self.queue_toggle.set_sensitive(False)
        self.replace_queue.set_enabled(False)

    ## Private methods ##

    # library and queue methods #

    def _confirm_play(self, tracks: TrackList, start_index: int, name: str):
        confirm_play = self.app.settings.get_boolean('confirm-play')
        play_request = PlayRequest(tracks, start_index)
        if self.player.state == 'stopped' or not confirm_play:
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

    # player specific methods #
    def _on_player_state_changed(self, _, state):
        if state in {'playing', 'paused'}:
            self.toolbar_view.set_reveal_bottom_bars(True)
            self.set_hide_on_close(
                self.app.settings.get_boolean('background-playback')
            )
            self.replace_queue.set_enabled(True)
            self.queue_toggle.set_sensitive(True)
            self.return_to_playing.set_enabled(True)
        else:
            self.set_hide_on_close(False)

    def _on_player_eos(self, _):
        if self.app.settings.get_boolean('clear-queue'):
            GLib.idle_add(self._exit_player, None)

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
        self.add_album = self._create_action('add-album', self.append_album)
        self.append_track = self._create_action(
            'append',
            self.append_track,
            enabled=True,
            parameter_type=GLib.VariantType('i'),
        )
        self.insert = self._create_action(
            'insert',
            self.insert_track,
            enabled=True,
            parameter_type=GLib.VariantType('i'),
        )

        self.replace_queue = self._create_action(
            'replace-queue', self.overwrite_queue
        )
        self.return_to_playing = self._create_action(
            'return-to-playing', self.return_to_playing
        )
        self.undo_queue = self._create_action(
            'undo-queue', self.undo, enabled=True
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

    def _create_action(
        self, name, callback, enabled=False, parameter_type=None
    ):
        action = Gio.SimpleAction.new(name, parameter_type)
        action.connect('activate', callback)
        action.set_enabled(enabled)
        self.add_action(action)
        return action
