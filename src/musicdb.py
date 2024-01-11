from gi.repository import GLib
import os
import sqlite3
from collections import namedtuple

from .items import TrackItem, AlbumItem, ArtistItem


ArtistTags = namedtuple('ArtistTags', ['name', 'sort', 'path'])
TrackTags = namedtuple(
    'TrackTags',
    [
        'title',
        'track',
        'disc',
        'discsubtitle',
        'album',
        'albumartist',
        'date',
        'length',
        'thumb',
        'cover',
        'path',
        'modified',
        'artists',
    ],
)


class MusicDB:
    def __init__(
        self, path=f'{GLib.get_user_data_dir()}/RecordBox/recordbox.db'
    ):
        if first_start := not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.cursor = self.db.cursor()
        if first_start:
            self._create_tables()
            self._create_views()

    def insert_track(self, track: TrackTags):
        self.cursor.execute(
            'INSERT INTO tracks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            track[:12],
        )

        # Albums switching between Various Artists and a single artist
        # need to be updated manually here to make sure all tracks in the album
        # get the change propagated. (E.g if no tracks have an albumartist tag an
        # the artist tag is deleted from a track, it becomes a Various Artists album,
        # but only one track was modified, so the Parser will only change that one track. Without
        # this update here, the rest of the tracks will still show up under the previous albumartist.)
        if albumartist := track[5]:
            if albumartist == '[Various Artists]':
                self.cursor.execute(
                    'UPDATE tracks SET albumartist = ? WHERE album = ? AND date = ?',
                    (albumartist, track[4], track[6]),
                )
            else:
                self.cursor.execute(
                    'UPDATE tracks SET albumartist = ? WHERE albumartist = "[Various Artists]" AND album = ? AND date = ?',
                    (albumartist, track[4], track[6]),
                )

        # Makes sure removed artists are actually removed from the database
        self.cursor.execute(
            'DELETE FROM artists WHERE path = ?',
            (track.path,),
        )
        self.cursor.executemany(
            'INSERT INTO artists VALUES (?, ?, ?)', track[12]
        )

    def commit(self):
        self.db.commit()

    def close(self):
        self.db.close()

    def remove_missing(self, root: str):
        self.cursor.execute('SELECT path FROM tracks')
        for path in self.cursor.fetchall():
            if not os.path.exists(path[0]) or not path[0].startswith(root):
                self.cursor.execute('DELETE FROM tracks WHERE path = ?', path)
        self.db.commit()

    def modify_time(self, path: str) -> float | None:
        self.cursor.execute(
            'SELECT modified FROM tracks WHERE path=?', (path,)
        )
        return result[0] if (result := self.cursor.fetchone()) else None

    def get_artists(self, all_artists=False) -> list[ArtistItem]:
        if all_artists:
            self.cursor.execute('SELECT * FROM [All Artists]')
        else:
            self.cursor.execute('SELECT * FROM [Album Artists]')
        return [ArtistItem(*artist) for artist in self.cursor.fetchall()]

    def get_albums(self) -> list[AlbumItem]:
        self.cursor.execute("""SELECT * FROM [Albums]""")
        albums = []
        for album in self.cursor.fetchall():
            self.cursor.execute(
                """SELECT DISTINCT name 
                    FROM artists NATURAL JOIN tracks
                    WHERE album = ? ORDER BY name""",
                (album[0],),
            )
            artists = [a[0] for a in self.cursor.fetchall()]
            tracks = self.get_tracks(album[0])
            albums.append(
                AlbumItem(**dict(album, artists=artists, tracks=tracks))
            )
        return albums

    def get_tracks(self, album: str) -> list[TrackItem]:
        self.cursor.execute(
            """SELECT track, title, discnumber as disc, discsubtitle, albumartist,
                length, path, thumb, cover
                FROM tracks 
                WHERE album = ? ORDER BY disc, track""",
            (album,),
        )
        tracks = []
        for track in self.cursor.fetchall():
            self.cursor.execute(
                'SELECT name FROM artists WHERE path = ? AND name != ?',
                (track[6], track[4]),
            )
            artists = ', '.join([a[0] for a in self.cursor.fetchall()])
            # remove None values
            track = {k: v for k, v in dict(track).items() if v is not None}
            tracks.append(TrackItem(**track, artists=artists, album=album))
        return tracks

    def _create_tables(self):
        self._execute_queries(
            """CREATE TABLE IF NOT EXISTS tracks(
                title TEXT NOT NULL,
                track TEXT NOT NULL,
                discnumber TEXT,
                discsubtitle TEXT,
                album TEXT NOT NULL,
                albumartist TEXT,
                date DATE,
                length REAL NOT NULL,
                thumb TEXT,
                cover TEXT,
                path TEXT NOT NULL,
                modified REAL NOT NULL,
                PRIMARY KEY (path) ON CONFLICT REPLACE)
            """,
            # artists needs a separate table because tracks can have multiple artists
            """CREATE TABLE IF NOT EXISTS artists(
                name TEXT NOT NULL,
                sort TEXT,
                path TEXT NOT NULL,
                PRIMARY KEY (path, name) ON CONFLICT REPLACE,
                FOREIGN KEY (path) REFERENCES tracks(path) ON DELETE CASCADE)
            """,
        )

    def _create_views(self):
        self._execute_queries(
            """CREATE VIEW [Albums] AS
            SELECT DISTINCT album as title, albumartist, SUM(length) as length, date, thumb, cover
            FROM tracks GROUP BY album, albumartist
            """,
            """CREATE VIEW [Album Artists] AS
            SELECT DISTINCT albumartist, sort, COUNT(DISTINCT album)
            FROM tracks NATURAL JOIN artists WHERE albumartist IS NOT NULL GROUP BY albumartist
            """,
            """CREATE VIEW [All Artists] AS
            SELECT DISTINCT name, sort, COUNT(DISTINCT album)
            FROM tracks NATURAL JOIN artists GROUP BY name""",
        )

    def _execute_queries(self, *queries: str):
        for query in queries:
            self.cursor.execute(query)
        self.db.commit()
