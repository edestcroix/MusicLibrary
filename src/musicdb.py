from gi.repository import GLib
import os
import sqlite3
from collections import namedtuple

from .items import TrackItem, AlbumItem, ArtistItem


ArtistTags = namedtuple('ArtistTags', ['name', 'sort', 'path'])
AlbumTags = namedtuple(
    'AlbumTags', ['name', 'artist', 'year', 'thumb', 'cover']
)
TrackTags = namedtuple(
    'TrackTags',
    [
        'title',
        'track',
        'discnumber',
        'discsubtitle',
        'album',
        'length',
        'path',
        'modified',
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
        self.cursor = self.db.cursor()
        if first_start:
            self._create_tables()
            self._create_views()

    def insert_artist(self, artist: ArtistTags):
        self.cursor.execute('INSERT INTO artists VALUES (?, ?, ?)', artist)

    def insert_album(self, album: AlbumTags):
        self.cursor.execute('INSERT INTO albums VALUES (?, ?, ?, ?, ?)', album)

    def insert_track(self, track: TrackTags):
        self.cursor.execute(
            'INSERT INTO tracks VALUES (?, ?, ?, ?, ?, ?, ?, ?)', track
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
                self.cursor.execute('DELETE FROM artists WHERE path= ?', path)
        self.db.commit()

        self.cursor.execute(
            'DELETE FROM albums WHERE name NOT IN (SELECT album FROM tracks)',
            (),
        )

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
        self.cursor.execute(
            """SELECT DISTINCT name, SUM(length), year, thumb, cover
                FROM albums JOIN tracks ON albums.name = tracks.album
                GROUP BY name ORDER BY year""",
        )
        albums = []
        for album in self.cursor.fetchall():
            self.cursor.execute(
                """SELECT DISTINCT name 
                    FROM artists NATURAL JOIN tracks
                    WHERE album = ? ORDER BY name""",
                (album[0],),
            )
            artists = [a[0] for a in self.cursor.fetchall()]
            tracks = self.get_tracks(album[0], album[3], album[4])
            albums.append(AlbumItem(*album, artists=artists, tracks=tracks))
        return albums

    def get_tracks(
        self, album: str, thumb: str, cover: str
    ) -> list[TrackItem]:
        self.cursor.execute(
            """SELECT track, title, discnumber, discsubtitle, length, path 
                FROM tracks 
                WHERE album = ? ORDER BY discnumber, track""",
            (album,),
        )
        tracks = []
        for track in self.cursor.fetchall():
            self.cursor.execute(
                'SELECT name FROM artists WHERE path = ?',
                (track[5],),
            )
            artists = [a[0] for a in self.cursor.fetchall()]
            self.cursor.execute(
                """SELECT artist FROM albums
                WHERE name = ?""",
                (album,),
            )
            if albumartist := self.cursor.fetchone():
                albumartist = albumartist[0]
            else:
                albumartist = artists[0] if artists else ''
            artists.remove(albumartist) if albumartist in artists else None
            artists = ', '.join(artists) or ''
            tracks.append(
                TrackItem(
                    *(track + (album, artists, albumartist, thumb, cover))
                )
            )
        return tracks

    def _create_tables(self):
        """Artist table stores the name of the artist, and the value of the artistsort tag found
        for the artist, if any. It also stores the path of the track file that the artist was found
        in. This way, all artists for each track can be stored.

        Album artists are then identified as
        artists that have their name in the artist column of the albums table. For the purposes
        of this application, album artists are either the value of the albumartist tag or the first
        artist encountered when parsing the file.

        Album table exists mainly to identify album artists and group album covers.

        Track table stores all track-specific metadata.

        """
        self._execute_queries(
            """CREATE TABLE IF NOT EXISTS artists(
                name TEXT NOT NULL, 
                sort TEXT, 
                path NOT NULL,
                UNIQUE(name, path) 
                ON CONFLICT REPLACE
            )""",
            """CREATE TABLE IF NOT EXISTS albums(
                name TEXT NOT NULL, 
                artist TEXT NOT NULL, 
                year DATE, 
                thumb TEXT, 
                cover TEXT, 
                UNIQUE(name, artist) 
                ON CONFLICT REPLACE
            )""",
            """CREATE TABLE IF NOT EXISTS tracks(
                title TEXT,
                track TEXT,
                discnumber TEXT,
                discsubtitle TEXT,
                album TEXT,
                length REAL,
                path TEXT,
                modified TIME,
                UNIQUE(path)
                ON CONFLICT REPLACE)
                """,
        )

    def _create_views(self):
        self._execute_queries(
            """CREATE VIEW [Album Artists] AS
                SELECT artists.name, sort, COUNT(DISTINCT albums.name)
                FROM artists JOIN albums ON artists.name = albums.artist 
                GROUP BY artists.name ORDER by artists.name
               """,
            """CREATE VIEW [ALL Artists] AS
                SELECT name, sort, COUNT(DISTINCT album)
                FROM artists NATURAL JOIN tracks
                GROUP BY name ORDER BY name
            """,
        )

    def _execute_queries(self, *queries: str):
        for query in queries:
            self.cursor.execute(query)
        self.db.commit()
