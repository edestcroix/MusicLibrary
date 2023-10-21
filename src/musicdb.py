from gi.repository import GLib
import os
import sqlite3

from .music_types import Album, Track
from .library import ArtistItem


StrOpt = str | None
FloatOpt = float | None
ArtistTags = tuple[str, StrOpt, StrOpt, StrOpt, bool]
AlbumTags = tuple[StrOpt, StrOpt, StrOpt, StrOpt]
TrackTags = tuple[StrOpt, StrOpt, StrOpt, StrOpt, float, str, FloatOpt]

# TODO: Start adding type hints to this file.
class MusicDB:
    def __init__(
        self, path=f'{GLib.get_user_data_dir()}/RecordBox/recordbox.db'
    ):
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(self.path)
        self.cursor = self.db.cursor()
        self._create_tables()

    def insert_artist(self, artist: ArtistTags):
        self.cursor.execute(
            'INSERT INTO artists VALUES (?, ?, ?, ?, ?)', artist
        )

    def insert_album(self, album: AlbumTags):
        self.cursor.execute('INSERT INTO albums VALUES (?, ?, ?, ?)', album)

    def insert_track(self, track: TrackTags):
        self.cursor.execute(
            'INSERT INTO tracks VALUES (?, ?, ?, ?, ?, ?, ?)', track
        )

    def commit(self):
        self.db.commit()

    def remove_missing(self):
        self.cursor.execute('SELECT path FROM tracks')
        for path in self.cursor.fetchall():
            if not os.path.exists(path[0]):
                self.cursor.execute('DELETE FROM tracks WHERE path = ?', path)
        self.db.commit()

        self._execute_queries(
            'DELETE FROM artists WHERE track_title NOT IN (SELECT title FROM tracks)',
            'DELETE FROM albums WHERE name NOT IN (SELECT album FROM tracks)',
        )

    def modify_time(self, path: str) -> float | None:
        self.cursor.execute(
            'SELECT modified FROM tracks WHERE path=?', (path,)
        )
        return result[0] if (result := self.cursor.fetchone()) else None

    def get_artists(self, all_artists=False) -> list[ArtistItem]:
        albumartist = '' if all_artists else ' WHERE albumartist = true'
        self.cursor.execute(
            f'SELECT DISTINCT name, sort, COUNT(DISTINCT album) FROM artists{albumartist} GROUP BY name ORDER BY name'
        )
        return [ArtistItem(*artist) for artist in self.cursor.fetchall()]

    def get_albums(self) -> list[Album]:
        self.cursor.execute(
            'SELECT DISTINCT name, COUNT(title), SUM(length), year, thumb, cover FROM albums JOIN tracks ON albums.name = tracks.album GROUP BY name ORDER BY year',
        )
        # Albums do not need to consider albumartist/artists, as they are only used to display the album list.
        # The library needs to have albums returned with all artists in the album's 'artist' field, because selecting
        # an artist will filter through the albums that have that artist in the 'artist' field.
        albums = []
        for album in self.cursor.fetchall():
            self.cursor.execute(
                'SELECT DISTINCT name FROM artists WHERE album = ? ORDER BY name',
                (album[0],),
            )
            artists = [a[0] for a in self.cursor.fetchall()]
            albums.append(Album(*(album + (artists,))))
        return albums

    def get_album(self, album: str) -> Album:
        self.cursor.execute(
            'SELECT name, COUNT(title), SUM(length), year, thumb, cover FROM albums JOIN tracks ON albums.name = tracks.album WHERE name = ? GROUP BY name',
            (album,),
        )
        result = self.cursor.fetchone()
        self.cursor.execute(
            'SELECT DISTINCT name FROM artists WHERE album = ? ORDER BY name',
            (album,),
        )
        artists = [a[0] for a in self.cursor.fetchall()]
        return Album(*(result + (artists,)))

    def get_tracks(self, album: Album) -> list[Track]:
        self.cursor.execute(
            'SELECT track, discnumber, title, length, path FROM tracks WHERE album = ? ORDER BY discnumber, track',
            (album.name,),
        )
        tracks = []
        # Tracks need to distinguish between artists and albumartists, so that additional artists can be displayed
        # in the track list. When fetching tracks from the DB the albumartist is therefore stored separately from the artists.
        for track in self.cursor.fetchall():
            self.cursor.execute(
                'SELECT name FROM artists WHERE track_title = ? AND album = ? AND albumartist = false',
                (track[2], album.name),
            )
            artists = [a[0] for a in self.cursor.fetchall()]
            self.cursor.execute(
                'SELECT name FROM artists WHERE track_title = ? AND album = ? AND albumartist = true',
                (track[2], album.name),
            )
            albumartist = self.cursor.fetchone()
            albumartist = albumartist[0] if albumartist else None
            tracks.append(Track(*(track + (album, artists, albumartist))))

        return tracks

    def _create_tables(self):
        self._execute_queries(
            """CREATE TABLE IF NOT EXISTS artists
                (name text, sort text, album text, track_title text, albumartist bool, UNIQUE(name, album, track_title) ON CONFLICT REPLACE)""",
            """CREATE TABLE IF NOT EXISTS albums
                (name text, year date, thumb text, cover text, UNIQUE(name, year) ON CONFLICT REPLACE)""",
            """CREATE TABLE IF NOT EXISTS tracks
                (title text, track text, discnumber text, album text, length real, path text, modified time, UNIQUE(path) ON CONFLICT REPLACE)
                """,
        )

    def _execute_queries(self, *queries: str):
        for query in queries:
            self.cursor.execute(query)
        self.db.commit()
