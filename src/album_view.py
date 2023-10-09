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

from .musicdb import MusicDB, Album


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/album_view.ui')
class RecordBoxAlbumView(Adw.Bin):
    __gtype_name__ = 'RecordBoxAlbumView'

    cover_image = Gtk.Template.Child()

    track_list = Gtk.Template.Child()

    album_box = Gtk.Template.Child()

    stack = Gtk.Template.Child()
    current_album = None

    _expand_discs = False

    @GObject.Property(type=bool, default=False)
    def expand_discs(self):
        return self._collapse_discs

    @expand_discs.setter
    def set_expand_discs(self, value):
        self._collapse_discs = value

    def set_breakpoint(self, _):
        self.album_box.set_orientation(Gtk.Orientation.VERTICAL)

    def unset_breakpoint(self, _):
        self.album_box.set_orientation(Gtk.Orientation.HORIZONTAL)

    def update_cover(self, cover_path):
        self.cover_image.set_from_file(cover_path)

    def clear_all(self):
        self.track_list.remove_all()

    def update_album(self, album: Album):
        self.current_album = album
        self.clear_all()
        self.update_cover(album.cover)
        self.update_tracks(album.get_tracks())

        self.stack.set_visible_child_name('album_view')

    def update_tracks(self, tracks):
        current_disc, disc_row = 0, None
        for track in tracks:
            if track.disc_num() != current_disc:
                current_disc = track.disc_num()
                disc_row = Adw.ExpanderRow(
                    title=f'Disc {current_disc}',
                    selectable=False,
                    expanded=self.expand_discs,
                )
                self.track_list.append(disc_row)
            row = self._create_row(
                track,
                icon_name='audio-x-generic-symbolic',
            )
            if disc_row:
                disc_row.add_row(row)
            else:
                self.track_list.append(row)

    def _track_sort_func(self, row1, row2):
        return row1.sort_key() > row2.sort_key()

    def _create_row(self, track, icon_name, parent_row=None):
        row = TrackRow(
            track=track,
            icon_name=icon_name,
        )
        row.set_title_lines(1)
        if parent_row:
            row.get_style_context().add_class('property')
            parent_row.add_row(row)

        return row


class TrackRow(Adw.ActionRow):
    def __init__(self, track, **kwargs):
        super().__init__(**kwargs)
        self.track = track
        self.set_title_lines(1)
        track_num = track.track_num()
        self.set_title(
            GLib.markup_escape_text(f'{track_num:0>2} - {track.title}')
        )
        self.set_subtitle(track.length_str())

    def sort_key(self):
        return (self.track.disc_num(), self.track.track_num())
