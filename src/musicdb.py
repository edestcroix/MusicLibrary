from gi.repository import GLib
import os
import sqlite3

from .library import AlbumItem, ArtistItem, TrackItem


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

    def close(self):
        self.db.close()

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

    def get_albums(self) -> list[AlbumItem]:
        self.cursor.execute(
            'SELECT DISTINCT name, SUM(length), year, thumb, cover FROM albums JOIN tracks ON albums.name = tracks.album GROUP BY name ORDER BY year',
        )
        albums = []
        for album in self.cursor.fetchall():
            self.cursor.execute(
                'SELECT DISTINCT name FROM artists WHERE album = ? ORDER BY name',
                (album[0],),
            )
            artists = [a[0] for a in self.cursor.fetchall()]
            tracks = self.get_tracks(album[0], album[3])
            albums.append(AlbumItem(*(album + (artists, tracks))))
        return albums

    def get_tracks(self, album: str, thumb: str) -> list[TrackItem]:
        self.cursor.execute(
            'SELECT track, discnumber, title, length, path FROM tracks WHERE album = ? ORDER BY discnumber, track',
            (album,),
        )
        tracks = []
        for track in self.cursor.fetchall():
            self.cursor.execute(
                'SELECT name FROM artists WHERE track_title = ? AND album = ? AND albumartist = false',
                (track[2], album),
            )
            artists = [a[0] for a in self.cursor.fetchall()]
            self.cursor.execute(
                'SELECT name FROM artists WHERE track_title = ? AND album = ? AND albumartist = true',
                (track[2], album),
            )
            albumartist = self.cursor.fetchone()
            albumartist = albumartist[0] if albumartist else None
            artists = ', '.join(artists)
            tracks.append(
                TrackItem(*(track + (album, artists, albumartist, thumb)))
            )
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
