from typing import Tuple
from gi.repository import GLib
from hashlib import sha256
from io import BytesIO
import mimetypes
import mutagen
import os
from PIL import Image
import contextlib

from .musicdb import MusicDB, AlbumInsert, ArtistInsert, TrackInsert

CoverPaths = Tuple[str, str]


class CoverImage:
    def __init__(self, image: bytes):
        self.image = image

    def sha256(self) -> str:
        return sha256(self.image).hexdigest()

    def cache_path(self) -> str:
        cache_dir = f'{GLib.get_user_cache_dir()}/RecordBox'
        return f'{cache_dir}/{self.sha256()}.png'

    def thumbnail(self) -> Image.Image:
        return self._resize(128)

    def large(self) -> Image.Image:
        return self._resize(512)

    def save(self) -> CoverPaths:
        return (self.save_thumbnail(), self.save_large())

    def save_thumbnail(self) -> str:
        path = self._save('/RecordBox/thumbnails')
        if not os.path.exists(path):
            image = self.thumbnail()
            image.save(path)
        return path

    def save_large(self) -> str:
        path = self._save('/RecordBox/large')
        if not os.path.exists(path):
            image = self.large()
            image.save(path)
        return path

    def _save(self, path):
        thumb_dir = f'{GLib.get_user_cache_dir()}{path}'
        result = f'{thumb_dir}/{self.sha256()}.png'
        if not os.path.exists(thumb_dir):
            os.makedirs(thumb_dir, exist_ok=True)
        return result

    def _resize(self, size):
        image = Image.open(BytesIO(self.image))
        image = image.convert('RGB')
        image.thumbnail((size, size))
        return image


class AudioFile:
    def __init__(self, audio, file: str):
        self.audio = audio
        self.file = file

    def try_key(self, key: str, all=False) -> str | list[str] | None:
        if key in self.audio:
            return self.audio[key] if all else self.audio[key][0]
        return None

    def album(self, cover_paths: CoverPaths | None) -> AlbumInsert:
        return AlbumInsert(
            self.try_key('album'),
            self.try_key('date'),
            cover_paths,
        )

    def artists(self) -> list[ArtistInsert]:
        albumartist = self.try_key('albumartist') or self.try_key('artist')
        artists = [
            ArtistInsert(
                artist,
                self.try_key('artistsort'),
                self.try_key('album'),
                self.try_key('title'),
                artist == albumartist,
            )
            for artist in self.audio['artist']
        ]
        if albumartist not in self.audio['artist']:
            artists.append(
                ArtistInsert(
                    albumartist,
                    self.try_key('artistsort'),
                    self.try_key('album'),
                    self.try_key('title'),
                    True,
                )
            )
        return artists

    def track(self) -> TrackInsert:
        return TrackInsert(
            self.try_key('title'),
            self.try_key('tracknumber'),
            self.try_key('discnumber'),
            self.try_key('album'),
            self.audio.info.length,
            self.file,
            os.path.getmtime(self.file),
        )

    def embedded_cover(self) -> CoverImage | None:
        if full := mutagen.File(self.file):
            if 'covr' in full.tags:
                return CoverImage(full.tags['covr'][0].data)
            elif 'APIC:' in full:
                return CoverImage(full.tags.get('APIC:').data)
            else:
                with contextlib.suppress(AttributeError):
                    return (
                        CoverImage(full.pictures[0].data)
                        if full.pictures
                        else None
                    )

    def check_need_update(self, mod_time: float) -> bool:
        return os.path.getmtime(self.file) > mod_time


class MusicParser:
    def __init__(self, path=os.path.expanduser('~/Music')):
        self._path = path

    def build(self, db: MusicDB):
        db.remove_missing()
        self._parse(db, self._path)
        print('Done!')

    def _parse(self, db: MusicDB, path: str):
        for root, _, files in os.walk(path):
            tracks, possible_covers = [], []
            for file in files:
                if audio := self._parse_audio(os.path.join(root, file)):
                    print(file)
                    tracks.append(audio)
                else:
                    possible_covers.append(os.path.join(root, file))

            external_cover = self._choose_cover(possible_covers)
            for track in tracks:
                self._send_to_db(db, track, external_cover)

    def _parse_audio(self, file: str) -> AudioFile | None:
        if (mime := self._mime_type(file)) and not mime.startswith('audio'):
            return None
        elif audio := mutagen.File(file, easy=True):
            return AudioFile(audio, file)

    def _mime_type(self, file: str) -> str | None:
        return mimetypes.guess_type(file)[0]

    def _choose_cover(self, images: list[str]) -> CoverImage | None:
        for image in images:
            # find the image called cover or folder and is a png or jpg
            if (
                image.lower().endswith('.png')
                or image.lower().endswith('.jpg')
                and ('cover' in image.lower() or 'folder' in image.lower())
            ):
                return CoverImage(open(image, 'rb').read())

    def _send_to_db(
        self, db: MusicDB, track: AudioFile, cover: CoverImage | None
    ):
        if track.check_need_update(db.modify_time(track.file)):
            cover = track.embedded_cover() or cover
            cover_paths = cover.save() if cover else None
            db.insert_track(track.track())
            db.insert_album(track.album(cover_paths))
            for artist in track.artists():
                db.insert_artist(artist)
