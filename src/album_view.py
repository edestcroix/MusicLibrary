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

    play_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    add_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    add_track_next = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    start_from_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

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
        row.connect('add_track', self._add_track)
        row.connect('add_track_next', lambda _, t: self.add_track_next.emit(t))
        row.connect('start_from_track', self._start_from_track)
        if disc_row:
            disc_row.add_row(row)
        else:
            self.track_list.append(row)

    def _play_track(self, _, track: TrackItem):
        self.emit('play_track', track)

    def _add_track(self, _, track: TrackItem):
        self.emit('add_track', track)

    def _start_from_track(self, _, track: TrackItem):
        if self.current_album:
            new_album = self.current_album.copy()
            new_album.tracks = new_album.tracks[
                new_album.tracks.index(track) :
            ]
            self.emit('start_from_track', new_album)


class TrackRow(Adw.ActionRow):

    play_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    add_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    start_from_track = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))
    add_track_next = GObject.Signal(arg_types=(GObject.TYPE_PYOBJECT,))

    def __init__(self, track: TrackItem, **kwargs):
        super().__init__(title_lines=1, selectable=False, **kwargs)
        self.track = track

        artists = f'\n{track.artists}' if (artists := track.artists) else ''
        self.set_title(
            GLib.markup_escape_text(
                f'{track.track:0>2} - {track.length}{artists}'
            )
        )
        self.set_subtitle(track.title)
        self.set_css_classes(self.get_css_classes() + ['property'])
        self.set_tooltip_text(track.raw_title)

        self.popover = self._create_popover()

        btn = Gtk.MenuButton()
        btn.set_icon_name('view-more-symbolic')
        btn.set_css_classes(['flat'])
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_popover(self.popover)

        self.add_suffix(btn)

    def _create_popover(self) -> Gtk.Popover:
        popover = Gtk.Popover.new()
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.set_css_classes(['menu'])
        box = Gtk.ListBox()
        box.append(self._create_menu_option(START_ICON, 'Play Track'))
        box.append(self._create_menu_option(START_ICON, 'Start Here'))
        box.append(self._create_menu_option(ADD_ICON, 'Insert Next'))
        box.append(self._create_menu_option(ADD_ICON, 'Append to Queue'))
        box.connect('row-activated', self._popover_selected)
        popover.set_child(box)
        return popover

    def _create_menu_option(self, icon_name: str, label: str) -> Gtk.Box:
        box = Gtk.Box()
        box.set_orientation(Gtk.Orientation.HORIZONTAL)
        box.set_halign(Gtk.Align.START)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        label = Gtk.Label(label=label, halign=Gtk.Align.START)
        box.append(icon)
        box.append(label)
        return box

    def _popover_selected(self, _, row: Gtk.ListBoxRow):
        self.popover.popdown()
        match row.get_index():
            case 0:
                self.emit('play_track', self.track)
            case 1:
                self.emit('start_from_track', self.track)
            case 2:
                self.emit('add_track_next', self.track)
            case 3:
                self.emit('add_track', self.track)
