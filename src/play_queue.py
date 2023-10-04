from gi.repository import Adw, Gtk, Gdk, GLib, Pango
import gi

gi.require_version('Gtk', '4.0')

from .musicrow import MusicRow


# TODO: Allow adding lone tracks to the queue. (Then allow for that in the UI)
# Highlight the current song in the queue. Connect this highlight function to some
# global signal that is emitted on track change.


class PlayQueue(Gtk.ListBox):
    __gtype_name__ = 'PlayQueue'

    current_track = None

    end = None
    start = None

    # Since AdwExpanderRows don't index their children, all the track rows
    # maintain a linked list of themselves so they when albums or tracks are removed
    # the continuity of the current track in the queue is maintained. New tracks
    # added to the end pointer, and tracks that are deleted update their neighbors
    # to point around them. Deleting an album preforms the track delete operations
    # on every track in the album starting at the first (Album ExpanderRows point
    # to first track in the album).

    def clear(self):
        self.remove_all()
        self.current_track = None

    def get_next_track(self):
        self.move_current('next', allow_none=True)
        return self.get_current_track()

    def get_current_track(self):
        return self.current_track.track if self.current_track else None

    def next(self):
        self.move_current('next')
        return self.current_track is not None

    def move_current(self, direction, allow_none=False):
        if direction == 'next' and self.current_track:
            if self.current_track.next:
                self._move_track_indicator(
                    self.current_track, self.current_track.next
                )
                self.current_track = self.current_track.next
            elif allow_none:
                self.current_track = None
        elif direction == 'prev' and self.current_track:
            if self.current_track.prev:
                self._move_track_indicator(
                    self.current_track, self.current_track.prev
                )
                self.current_track = self.current_track.prev
            elif allow_none:
                self.current_track = None

    def previous(self):
        self.move_current('prev')
        return self.current_track is not None

    def add_album(self, album):
        album_row = PlayQueueAlbumRow(album.name, album.artist, album.cover)
        album_row.set_tracks(album.tracks)
        album_row.remove_button.connect(
            'clicked',
            lambda r: self._remove_album(r.get_ancestor(PlayQueueAlbumRow)),
        )

        row = None
        prev = None

        start_row = PlayQueueTrackRow(album.tracks[0])
        row = start_row
        start_row.remove_button.connect(
            'clicked',
            lambda r: self._remove(
                album_row, r.get_ancestor(PlayQueueTrackRow)
            ),
        )
        if not self.current_track:
            self.current_track = start_row
            start_row.add_prefix(
                Gtk.Image.new_from_icon_name('media-playback-start-symbolic')
            )
        elif self.end:
            self.end.set_next(start_row)
            start_row.set_prev(self.end)

        if not self.start:
            self.start = start_row

        album_row.set_first(start_row)
        album_row.add_row(start_row)

        for track in album.tracks[1:]:
            prev = row
            row = PlayQueueTrackRow(track)
            self._setup_row(row, album_row, prev)

        self.end = row

        self.append(album_row)

    def _setup_row(self, row, album_row, prev):
        row.set_prev(prev)
        if prev:
            prev.set_next(row)

        album_row.add_row(row)
        row.remove_button.connect(
            'clicked',
            lambda r: self._remove(
                album_row, r.get_ancestor(PlayQueueTrackRow)
            ),
        )

    def _move_track_indicator(self, cur, next):
        if next:
            cur.remove_prefix() if cur else None
            next.add_prefix(
                Gtk.Image.new_from_icon_name('media-playback-start-symbolic')
            )

    def _remove(self, album_row, row):

        # Don't remove the current track
        if self.current_track == row:
            return

        if self.end == row:
            self.end = row.prev

        if album_row.first == row:
            album_row.set_first(row.next)

        row.prev.set_next(row.next) if row.prev else None
        row.next.set_prev(row.prev) if row.next else None

        album_row.remove(row)
        if album_row.num_tracks == 0:
            self.remove(album_row)

    def _remove_album(self, album_row):
        cur = album_row.first
        for _ in range(album_row.num_tracks):
            next_cur = cur.next
            self._remove(album_row, cur)
            cur = next_cur


# Subclass of an AdwExpanderRow that allows Albums to be collapsed in the
# play queue. Since AdwExpanderRows don't index their children, AlbumRows
# store a pointer to their first child track. Tracks store pointers to their
# neighbors in the queue.
class PlayQueueAlbumRow(Adw.ExpanderRow):
    __gtype_name__ = 'PlayQueueAlbumRow'

    first = None

    num_tracks = 0

    def __init__(self, title=None, subtitle=None, cover=None):
        super().__init__()
        self.set_title(GLib.markup_escape_text(title))
        self.set_subtitle(GLib.markup_escape_text(subtitle))
        self.set_title_lines(1)
        self.remove_button = Gtk.Button()
        self.remove_button.get_style_context().add_class('flat')
        self.remove_button.set_icon_name('list-remove-symbolic')
        self.remove_button.set_tooltip_text('Remove from queue')
        self.add_suffix(self.remove_button)

        if cover:
            image = Gtk.Image()
            image.set_from_file(cover)
            image.set_pixel_size(32)
            self.add_prefix(image)

    def set_first(self, first):
        self.first = first

    def set_tracks(self, tracks):
        self.tracks = tracks

    def add_row(self, row):
        self.num_tracks += 1
        super().add_row(row)

    def remove(self, row):
        self.num_tracks -= 1
        super().remove(row)


class PlayQueueTrackRow(Adw.ActionRow):
    __gtype_name__ = 'PlayQueueTrackRow'

    prev = None
    next = None

    def __init__(self, track):
        self.track = track
        super().__init__()

        self.set_title(GLib.markup_escape_text(track.title))
        self.remove_button = Gtk.Button()
        self.remove_button.get_style_context().add_class('flat')
        self.remove_button.set_icon_name('list-remove-symbolic')
        self.remove_button.set_tooltip_text('Remove from queue')
        self.add_suffix(self.remove_button)

    def set_prev(self, prev):
        self.prev = prev

    def set_next(self, next):
        self.next = next

    def add_prefix(self, widget):
        self.prefix = widget
        super().add_prefix(widget)

    def remove_prefix(self):
        super().remove(self.prefix)
