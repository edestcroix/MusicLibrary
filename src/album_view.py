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

from gi.repository import Adw, Gtk, GLib
import gi
import re

gi.require_version('Gtk', '4.0')

from .musicdb import MusicDB, Album


@Gtk.Template(resource_path='/ca/edestcroix/MusicLibary/album_view.ui')
class MusicLibraryAlbumView(Adw.Bin):
    __gtype_name__ = 'MusicLibraryAlbumView'

    cover_image = Gtk.Template.Child()

    track_list = Gtk.Template.Child()

    album_box = Gtk.Template.Child()

    stack = Gtk.Template.Child()
    current_album = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.track_list.set_sort_func(self._track_sort_func)

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
        for track in tracks:
            track_num = re.sub(r'/.*', '', track.track)
            disc_num = (
                re.sub(r'/.*', '', track.discnumber) + '/'
                if track.discnumber
                else ''
            )
            if disc_num:
                title = f'{disc_num:0>2}{track_num:0>2} - {track.title}'
            else:
                title = f'{track_num:0>2} - {track.title}'
            row = self._create_row(
                title=title,
                subtitle=f'{int(track.length // 60):02}:{int(track.length % 60):02}',
                icon_name='audio-x-generic-symbolic',
            )
            self.track_list.append(row)

    def _track_sort_func(self, row1, row2):
        # get string inside parentheses
        seg1 = re.search(r'(.*?)-', row1.get_title())
        seg2 = re.search(r'(.*?)-', row2.get_title())

        if not seg1 or not seg2:
            return False
        num1, num2 = 0, 0
        if set1 := seg1[1].split('/'):
            num1 = int(set1[0])
        if set2 := seg2[1].split('/'):
            num2 = int(set2[0])

        return num1 > num2

    def _create_row(self, title, subtitle, icon_name, parent_row=None):
        row = Adw.ActionRow(
            title=GLib.markup_escape_text(title),
            subtitle=GLib.markup_escape_text(subtitle),
            icon_name=icon_name,
        )
        row.set_title_lines(1)
        if parent_row:
            row.get_style_context().add_class('property')
            parent_row.add_row(row)

        return row
