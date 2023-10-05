import contextlib
from dataclasses import dataclass
from gi.repository import GLib
from hashlib import sha256
from io import BytesIO
import mimetypes
import mutagen
import os
from PIL import Image
import re
import sqlite3


@dataclass
class Album:
    name: str
    num_tracks: int
    length: int
    date: str
    artist: str
    cover: str

    def get_tracks(self):
        return self.tracks

    def set_tracks(self, tracks):
        self.tracks = tracks
        # sort tracks by their track number (which might be in the form 1/10)
        self.tracks.sort(key=self._sort_tracks)

    def _sort_tracks(self, t):
        if t.discnumber is None:
            return int(t.track.split('/')[0])
        discnum = int(t.discnumber.split('/')[0])
        tracknum = int(t.track.split('/')[0])
        return discnum * 100 + tracknum

    def to_row(self):
        return (
            self.name,
            f'{self.length_str()} - {self.num_tracks} tracks',
            self.artist,
            self.cover,
            str(self.date),
        )

    def length_str(self):
        return f'{int(self.length // 3600):02}:{int(self.length // 60 % 60):02}:{int(self.length % 60):02}'


@dataclass
class Artist:
    name: str
    num_albums: int

    def to_row(self):
        return (
            self.name,
            f'{self.num_albums} albums',
        )


@dataclass
class Track:
    track: str
    discnumber: str
    title: str
    length: int
    path: str
    album: str

    def to_row(self):
        return (self.track, self.title, self.length, self.path)

    def disc_num(self):
        return (
            int(re.sub(r'/.*', '', self.discnumber)) if self.discnumber else 0
        )

    def track_num(self):
        return int(re.sub(r'/.*', '', self.track)) if self.track else 0


class MusicDB:
    def __init__(self):

        if not os.path.exists(f'{GLib.get_user_cache_dir()}/recordbox'):
            os.mkdir(f'{GLib.get_user_cache_dir()}/recordbox')

        if not os.path.exists(f'{GLib.get_user_data_dir()}/recordbox'):
            os.mkdir(f'{GLib.get_user_data_dir()}/recordbox')

        self.conn = sqlite3.connect(
            f'{GLib.get_user_data_dir()}/recordbox/music.db'
        )
        self.c = self.conn.cursor()

        self.c.execute(
            """CREATE TABLE IF NOT EXISTS albums
                (name text, artist text, year date, cover text, UNIQUE(name, artist) ON CONFLICT REPLACE)
                """
        )
        self.c.execute(
            """
                CREATE TABLE IF NOT EXISTS tracks
                (title text, track text, discnumber text, album text, length real, path text, modified time, UNIQUE(album, track, discnumber) ON CONFLICT REPLACE)
                """
        )

    def get_artists(self):
        self.c.execute(
            'SELECT DISTINCT artist, COUNT(DISTINCT name) FROM albums GROUP BY artist'
        )
        return [Artist(*a) for a in self.c.fetchall()]

    def get_albums(self):
        self.c.execute(
            'SELECT DISTINCT name, COUNT(title), SUM(length), year, artist, cover FROM albums JOIN tracks ON albums.name = tracks.album GROUP BY name ORDER BY year',
        )
        return [Album(*a) for a in self.c.fetchall()]

    def get_album(self, album):
        self.c.execute(
            'SELECT name, COUNT(title), SUM(length), year, artist, cover FROM albums JOIN tracks ON albums.name = tracks.album WHERE name = ? GROUP BY name',
            (album,),
        )
        return Album(*self.c.fetchone())

    def get_tracks(self, album):
        self.c.execute(
            'SELECT track, discnumber, title, length, path FROM tracks WHERE album = ? ORDER BY discnumber, track',
            (album.name,),
        )
        return [Track(*(t + (album,))) for t in self.c.fetchall()]

    def sync_library(self, path='~/Music'):
        self._remove_missing(self._find_missing())
        self._parse_library(path)

    def _parse_library(self, path='~/Music'):

        current_dir = list(os.scandir(os.path.expanduser(path)))

        directories = [entry for entry in current_dir if entry.is_dir()]

        images = [
            entry
            for entry in current_dir
            if (mimetype := mimetypes.guess_type(entry.path)[0])
            and mimetype.startswith('image')
        ]

        to_insert = []

        for entry in directories:
            self._parse_library(entry.path)

        embed_cover = None
        for file in [f for f in current_dir if f.is_file()]:
            self._sync_file(file, to_insert)
            embed_cover = self._get_embeded_cover(file) or embed_cover

        cached_cover_path = None
        if cover := embed_cover or self._find_cover(images):
            cached_cover_path = self._cache_cover(cover)

        self._insert_to_db(to_insert, cached_cover_path)

    def _sync_file(self, file, to_insert):
        if (
            mimetype := mimetypes.guess_type(file)[0]
        ) and not mimetype.startswith('audio'):
            return
        path = file.path

        self.c.execute('SELECT modified FROM tracks WHERE path = ?', (path,))
        modified = self.c.fetchone()
        if modified and modified[0] >= file.stat().st_mtime:
            return
        self.c.execute('DELETE FROM tracks WHERE path = ?', (path,))
        self.conn.commit()
        if audio := mutagen.File(file.path, easy=True):
            to_insert.append((file, audio))

    def _find_cover(self, images):
        cover = next(
            (
                image.path
                for image in images
                if image.name.lower()[:-4] in ('cover', 'folder', 'front')
            ),
            None,
        )
        if not cover and images:
            cover = images[0].path
        return cover

    def _get_embeded_cover(self, audio_path):
        embed_cover = None
        if full := mutagen.File(audio_path.path):
            if 'covr' in full.tags:
                embed_cover = full.tags['covr'][0].data
            elif 'APIC:' in full:
                embed_cover = full.tags.get('APIC:').data
            else:
                with contextlib.suppress(AttributeError):
                    embed_cover = (
                        full.pictures[0].data if full.pictures else None
                    )
        return embed_cover

    def _cache_cover(self, cover):
        cache_name = self._hash_cover(cover)
        cover = BytesIO(cover) if type(cover) == bytes else cover
        cached_cover_path = (
            f'{GLib.get_user_cache_dir()}/recordbox/{cache_name}.jpg'
        )
        if not os.path.exists(cached_cover_path):
            self._create_thumbnail(cover, cached_cover_path)
        return cached_cover_path

    def _hash_cover(self, cover):
        if type(cover) == str:
            return sha256(open(cover, 'rb').read()).hexdigest()
        elif type(cover) == bytes:
            return sha256(cover).hexdigest()

    def _create_thumbnail(self, cover, out_path):
        img = Image.open(cover)
        rgb_img = img.convert('RGB')
        rgb_img.thumbnail((320, 320))
        rgb_img.save(out_path)

    def _insert_to_db(self, to_insert, cover):
        for (entry, audio) in to_insert:
            self._insert(
                'albums',
                self._try_key(audio, 'album'),
                self._try_key(audio, 'artist'),
                self._try_key(audio, 'date') or self._try_key(audio, 'year'),
                cover,
            )
            self._insert(
                'tracks',
                self._try_key(audio, 'title'),
                self._try_key(audio, 'tracknumber'),
                self._try_key(audio, 'discnumber'),
                self._try_key(audio, 'album'),
                audio.info.length,
                entry.path,
                entry.stat().st_mtime,
            )
            self.conn.commit()

    def _try_key(self, audio, key):
        try:
            return audio[key][0]
        except KeyError:
            return None

    def _insert(self, table, *args):
        self.c.execute(
            f'INSERT INTO {table} VALUES ({", ".join(["?"] * len(args))})',
            args,
        )

    def _find_missing(self):
        self.c.execute('SELECT path FROM tracks')
        return [
            path[0]
            for path in self.c.fetchall()
            if not os.path.exists(path[0])
        ]

    def _remove_missing(self, paths):
        for path in paths:
            self.c.execute('DELETE FROM tracks WHERE path = ?', (path,))
            self.conn.commit()

        self.c.execute(
            'DELETE FROM albums WHERE name NOT IN (SELECT DISTINCT album FROM tracks)'
        )
        self.conn.commit()
