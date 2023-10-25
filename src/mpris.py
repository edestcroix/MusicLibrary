from gi.repository import Gio, Gst, GLib, Gtk
from mpris_server.adapters import MprisAdapter
from mpris_server.events import EventAdapter
from mpris_server.base import Album, Track, PlayState, Artist


class Mpris(MprisAdapter):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.name = 'RecordBox'
        self.app = app
        self.app_player = self.app.player()

    def can_fullscreen(self):
        return False

    def can_quit(self):
        return False

    def can_raise(self):
        return True

    def set_raise(self, _):
        self.app.props.active_window.present()

    def get_desktop_entry(self):
        return 'com.github.edestcroix.RecordBox'

    def get_fullscreen(self):
        return False

    def get_mime_types(self):
        return [
            'application/ogg',
            'audio/x-vorbis+ogg',
            'audio/x-flac',
            'audio/mpeg',
        ]

    def get_uri_schemes(self):
        return ['file']

    def has_tracklist(self):
        return False

    def get_identity(self):
        return 'RecordBox'

    def get_playstate(self):
        state = self.app_player.state
        if state == 'ready':
            state = 'paused'

        return PlayState[state.upper()]

    def quit(self):
        self.app.quit()

    def get_current_track(self):
        if track := self.app_player._play_queue.playing_track():
            return Track(
                name=track.title,
                artists=(Artist(name=track.albumartist),),
                album=Album(name=track.album),
                length=self.app_player.get_duration(),
                disc_no=track.discnumber,
                uri=f'file://{track.path}',
                track_no=track.track,
            )

    def _has_track(self):
        return self.app_player._play_queue.get_current_track() is not None

    def can_control(self):
        return self._has_track()

    def can_go_next(self):
        return self._has_track()

    def can_go_previous(self):
        return self._has_track()

    def can_pause(self):
        return self._has_track()

    def can_play(self):
        return self._has_track()

    def can_seek(self):
        return self._has_track()

    def get_art_url(self, _):
        if track := self.app_player._play_queue.playing_track():
            return f'file://{track.thumb}'

    def get_current_position(self):
        return self.app_player.get_progress()

    def get_maxiumum_rate(self):
        return 1.0

    def get_minimum_rate(self):
        return 1.0

    def get_stream_title(self):
        if track := self.app_player._play_queue.playing_track():
            return track.title
        else:
            return ''

    def get_volume(self):
        return self.app_player.volume

    def get_rate(self):
        return 1.0

    def is_mute(self):
        return self.app_player.muted

    def is_playlist(self):
        return False

    def is_repeating(self):
        return self.app_player._play_queue.loop

    def pause(self):
        if self.app_player.state == 'playing':
            self.app_player.toggle()

    def play(self):
        if self.app_player.state == 'paused':
            self.app_player.toggle()

    def play_pause(self):
        self.app_player.toggle()

    def stop(self):
        self.app_player.stop()

    def next(self):
        playing = self.app_player.state == 'playing'
        self.app_player.go_next()
        if not playing:
            self.app_player.toggle()

    def previous(self):
        playing = self.app_player.state == 'playing'
        self.app_player.go_previous()
        if not playing:
            self.app_player.toggle()

    def resume(self):
        if self.app_player.state == 'paused':
            self.app_player.toggle()

    def seek(self, time, _):
        self.app_player.seek(time)

    def set_repeating(self, val):
        self.app_player.loop = val

    def set_mute(self, val):
        self.app_player.muted = val

    def set_volume(self, val):
        self.app_player.volume = val


class MprisEventHandler(EventAdapter):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.app_player = self.app.props.active_window.main_view.player

        self.app_player.connect('state-changed', self._on_state_changed)
        self.app_player.connect('stream-start', self._on_stream_start)
        self.app_player.connect('notify::volume', self._on_volume_changed)

    def _on_state_changed(self, player, state):
        if state in ('playing', 'paused'):
            self.on_playpause()
        if state == 'stopped':
            self.on_ended()
            self.on_options()

    def _on_stream_start(self, player):
        self.on_playpause()
        self.on_playback()
        self.on_options()

    def _on_volume_changed(self, player, _):
        self.on_volume()
