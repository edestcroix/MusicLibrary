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

from gi.repository import Adw, Gtk, GLib, GObject
import gi

gi.require_version('Gtk', '4.0')

from .library import AlbumItem, TrackItem


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/album_view.ui')
class RecordBoxAlbumView(Adw.Bin):
    __gtype_name__ = 'RecordBoxAlbumView'

    cover_image = Gtk.Template.Child()

    track_list = Gtk.Template.Child()

    album_box = Gtk.Template.Child()

    stack = Gtk.Template.Child()
    current_album = None

    expand_discs = GObject.Property(type=bool, default=False)

    play_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    add_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    def set_breakpoint(self, _):
        self.album_box.set_orientation(Gtk.Orientation.VERTICAL)

    def unset_breakpoint(self, _):
        self.album_box.set_orientation(Gtk.Orientation.HORIZONTAL)
    start_from_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    def update_cover(self, cover_path):
        self.cover_image.set_from_file(cover_path)

    def clear_all(self):
        self.track_list.remove_all()

    def update_album(self, album: AlbumItem, current_artist=None):
        self.current_album = album
        self.clear_all()
        self.update_cover(album.cover)
        self.update_tracks(album.tracks, current_artist)
        self.stack.set_visible_child_name('album_view')

    def update_tracks(self, tracks: list[TrackItem], current_artist):
        current_disc, disc_row = 0, None
        for track in tracks:
            if track.discnumber != current_disc:
                disc_row = self._disc_row(current_disc := track.discnumber)
            self._setup_row(track, disc_row, current_artist)

    def _disc_row(self, current_disc):
        disc_row = Adw.ExpanderRow(
            title=f'Disc {current_disc}',
            selectable=False,
            expanded=self.expand_discs,
        )
        self.track_list.append(disc_row)
        return disc_row

    def _setup_row(self, track: TrackItem, disc_row, current_artist):
        row = self._create_row(track, current_artist)
        row.connect('play_track', self._play_track)
        row.connect('add_track', self._add_track)
        row.connect('start_from_track', self._start_from_track)
        if disc_row:
            disc_row.add_row(row)
        else:
            self.track_list.append(row)

    def _create_row(self, track: TrackItem, current_artist, parent_row=None):
        row = TrackRow(track=track, current_artist=current_artist)
        row.set_title_lines(1)
        row.set_selectable(False)
        if parent_row:
            row.get_style_context().add_class('property')
            parent_row.add_row(row)
        return row

    def _play_track(self, _, track):
        self._track_signal(track, 'play_track')

    def _add_track(self, _, track):
        self._track_signal(track, 'add_track')

    def _start_from_track(self, _, track):
        if self.current_album:
            new_album = self.current_album.copy()
            new_album.tracks = new_album.tracks[
                new_album.tracks.index(track) :
            ]
            self.emit('start_from_track', new_album)

    def _track_signal(self, track, signal):
        # Play queue currently can only add albums, not lone tracks,
        # so we create a new album with only the desired track in it.
        if self.current_album:
            new_album = self.current_album.copy()
            new_album.tracks = [track]
            self.emit(signal, new_album)


class TrackRow(Adw.ActionRow):

    play_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    add_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    start_from_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    def __init__(self, track: TrackItem, current_artist, **kwargs):
        super().__init__(**kwargs)
        self.track = track
        track_num = track.track
        self.set_title_lines(1)
        self.set_title(track.title)

        if current_artist and track.albumartist != current_artist:
            if track.artists:
                artists = f'\n{track.albumartist}, {track.artists}'
            else:
                artists = f'\n{track.albumartist}'
        elif artists := track.artists:
            artists = f'\n{track.artists}'
        else:
            artists = ''
        self.set_subtitle(
            GLib.markup_escape_text(
                f'{track_num:0>2} - {track.length}{artists}'
            )
        )
        self.set_tooltip_text(track.title)
        btn = Gtk.MenuButton()
        btn.set_icon_name('view-more-symbolic')
        btn.set_css_classes(['flat'])
        btn.set_valign(Gtk.Align.CENTER)
        self.popover = self._create_popover()
        btn.set_popover(self.popover)
        self.add_suffix(btn)

    def sort_key(self):
        return (self.track.disc_num(), self.track.track_num())

    def _create_button(self, icon_name, callback, title, args=None):
        button, content = Gtk.Button(), Adw.ButtonContent()
        content.set_label(title)
        content.set_icon_name(icon_name)
        button.set_child(content)
        button.set_css_classes(['flat'])
        if args:
            button.connect('clicked', callback, args)
        else:
            button.connect('clicked', callback)
        return button

    def _create_popover(self):
        popover = Gtk.Popover.new()
        popover.set_position(Gtk.PositionType.BOTTOM)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(
            self._create_button(
                'media-playback-start-symbolic',
                self._popover_selected,
                'Play track',
                'play_track',
            )
        )
        box.append(
            self._create_button(
                'media-playback-start-symbolic',
                self._popover_selected,
                'Start from track',
                'start_from_track',
            )
        )
        box.append(
            self._create_button(
                'list-add-symbolic',
                self._popover_selected,
                'Add to queue',
                'add_track',
            )
        )
        popover.set_child(box)
        return popover

    def _popover_selected(self, _, action):
        self.popover.popdown()
        self.emit(action, self.track)
