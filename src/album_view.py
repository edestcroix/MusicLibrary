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

from collections import namedtuple
from gi.repository import Adw, Gtk, GLib, GObject, Gio
import gi

gi.require_version('Gtk', '4.0')

from .items import AlbumItem, TrackItem

START_ICON = 'media-playback-start-symbolic'
ADD_ICON = 'list-add-symbolic'


@Gtk.Template(resource_path='/com/github/edestcroix/RecordBox/album_view.ui')
class AlbumView(Adw.BreakpointBin):
    __gtype_name__ = 'RecordBoxAlbumView'

    cover_image = Gtk.Template.Child()

    track_list = Gtk.Template.Child()

    album_box = Gtk.Template.Child()

    album_title = Gtk.Template.Child()
    album_artist = Gtk.Template.Child()

    stack = Gtk.Template.Child()
    current_album = None

    expand_discs = GObject.Property(type=bool, default=False)

    def update_cover(self, cover_path: str):
        self.cover_image.set_from_file(cover_path)

    def clear_all(self):
        self.track_list.remove_all()

    def update_album(self, album: AlbumItem):
        self.current_album = album
        self.clear_all()
        self.update_cover(album.cover)
        self.update_tracks(album.tracks)
        self.album_title.set_text(album.raw_name)
        self.album_artist.set_text(album.artists[0])
        self.stack.set_visible_child_name('album_view')

    def update_tracks(self, tracks: list[TrackItem]):
        current_disc, disc_row = 0, None
        for track in tracks:
            if track.discnumber != current_disc:
                disc_row = self._disc_row(
                    current_disc := track.discnumber, track.discsubtitle
                )
            self._setup_row(track, disc_row)

    def _disc_row(self, current_disc: int, discsubtitle: str | None):
        disc_row = Adw.ExpanderRow(
            title=f'Disc {current_disc}',
            subtitle=discsubtitle,
            selectable=False,
            expanded=self.expand_discs,
        )
        if discsubtitle:
            disc_row.set_css_classes(disc_row.get_css_classes() + ['property'])
        self.track_list.append(disc_row)
        return disc_row

    def _setup_row(self, track: TrackItem, disc_row: Adw.ExpanderRow):
        row = TrackRow(track=track)
        row.connect('play_track', self._play_track)
        row.connect('add_track', lambda _, t: self.add_track.emit(t))
        row.connect('add_track_next', lambda _, t: self.add_track_next.emit(t))
        if disc_row:
            disc_row.add_row(row)
        else:
            self.track_list.append(row)

    def _play_track(self, _, track: TrackItem):
        if album := self.current_album:
            self.emit(
                'play_request',
                PlayRequest(album.tracks, album.tracks.index(track)),
            )


class TrackRow(Adw.ActionRow):

    play_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    add_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    start_from_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    add_track_next = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    def __init__(self, track: TrackItem, **kwargs):
        super().__init__(title_lines=1, selectable=False, **kwargs)
        self.track = track

        artists = f'\n{track.artists}' if track.artists else ''
        self.set_subtitle(
            GLib.markup_escape_text(
                f'{track.track:0>2} - {track.length}{artists}'
            )
        )
        self.set_title(track.title)
        self.set_tooltip_text(track.raw_title)

        self.menu_model = Gio.Menu.new()
        self.menu_model.append('Play Track', f'win.play({track.track - 1})')
        self.menu_model.append(
            'Add to Queue', f'win.append({track.track - 1})'
        )
        self.menu_model.append('Insert Next', f'win.insert({track.track - 1})')
        self.new_popover = Gtk.PopoverMenu.new_from_model(self.menu_model)

        btn = Gtk.MenuButton()
        btn.set_icon_name('view-more-symbolic')
        btn.set_css_classes(['flat'])
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_popover(self.new_popover)

        self.add_suffix(btn)
