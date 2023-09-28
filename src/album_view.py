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

from .musicdb import MusicDB


@Gtk.Template(resource_path='/ca/edestcroix/MusicLibary/album_view.ui')
class MusicLibraryAlbumView(Gtk.Box):
    __gtype_name__ = 'MusicLibraryAlbumView'

    cover_image = Gtk.Template.Child()

    track_list = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_cover(self, cover_path):
        self.cover_image.set_from_file(cover_path)

    def update_tracks(self, tracks):
        self.track_list.remove_all()
        for track in tracks:
            row = Adw.ActionRow(
                title=GLib.markup_escape_text(track[1]),
                # format as mm:ss
                subtitle=f'{int(track[2] // 60):02}:{int(track[2] % 60):02}',
                # secondary_text=track[2],
                icon_name='audio-x-generic-symbolic',
            )
            self.track_list.append(row)
