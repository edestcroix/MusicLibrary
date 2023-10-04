"""Gstreamer API."""

import logging
import multiprocessing
import os
import queue
import time
import urllib
import urllib.parse

import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst


Gst.init(None)


class Player:
    def __init__(self, play_queue):
        self._player = Gst.parse_launch(
            'playbin audio-sink="rgvolume album-mode=\\"true\\" ! autoaudiosink"'
        )
        self._player.connect('about-to-finish', self._on_about_to_finish)
        self.bus = self._player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message', self._on_message)
        self._play_queue = play_queue
        self.state = 'stopped'

    def play(self):
        url = self._prepare_url(self._play_queue.get_current_track())
        self._player.set_state(Gst.State.NULL)
        time.sleep(0.1)
        self._player.set_property('uri', url)
        self._player.set_state(Gst.State.PLAYING)
        self.state = 'playing'

    def toggle(self):
        if self._player.get_state(1 * Gst.SECOND)[1] == Gst.State.PLAYING:
            self._player.set_state(Gst.State.PAUSED)
            self.state = 'paused'
        elif self._player.get_state(1 * Gst.SECOND)[1] == Gst.State.PAUSED:
            self._player.set_state(Gst.State.PLAYING)
            self.state = 'playing'

    def get_progress(self):
        return self._player.query_position(Gst.Format.TIME)[1]

    def get_duration(self):
        return self._player.query_duration(Gst.Format.TIME)[1]

    # TODO: Either here or in the main_view, prevent too frequent
    # seeking caused by the scale being scrolled too fast (because it makes
    # awful noises)
    def seek(self, position):
        duration = self._player.query_duration(Gst.Format.TIME)[1]
        if position > duration:
            return
        else:
            self._player.seek_simple(
                Gst.Format.TIME, Gst.SeekFlags.FLUSH, position
            )

    def _on_about_to_finish(self, _):
        if next_track := self._play_queue.get_next_track():
            self._player.set_property('uri', self._prepare_url(next_track))

    def _prepare_url(self, track):
        path = os.path.realpath(track.path.strip())
        result = urllib.parse.ParseResult(
            scheme='file',
            path=path,
            netloc='',
            query='',
            fragment='',
            params='',
        )
        result = urllib.parse.urlunparse(result)
        return result

    def _on_message(self, _, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self._player.set_state(Gst.State.NULL)
            self.state = 'stopped'
        elif t == Gst.MessageType.ERROR:
            self._player.set_state(Gst.State.NULL)
            err, debug = message.parse_error()
            print(f'Error: {err}', debug)
