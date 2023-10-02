"""Gstreamer API."""

import logging
import multiprocessing
import os
import queue
import time
import urllib
import urllib.request

import gi

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst


Gst.init(None)

# TODO: Play queue supoprt. Should it be stored in the Player, and the UI
# mirror it, or should the UI store the queue and then send the songs to the
# player? (Probably the latter) Gapless will be interesting. Will have to
# get the next song out of the play queue when the about-to-finsh signal is
# emitedd (will have to listen for that signal too) and queue it up somehow.
# Don't know if this can be done with one player, or by queueing up the next
# song in a second player and swapping them out when the current one finishes.


class Player:
    def __init__(self, bus_callback=None):
        """Initialize the player."""
        self._player = Gst.ElementFactory.make('playbin', 'player')
        self.bus = self._player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message', self.on_message)

    def play(self, track):
        """Start playback."""
        file_path = os.path.realpath(track[3].strip())
        self._player.set_state(Gst.State.NULL)
        self._player.set_property('uri', f'file:/{file_path}')
        self._player.set_state(Gst.State.PLAYING)
        print(self._player.get_state(1 * Gst.SECOND))

    def on_message(self, _, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self._player.set_state(Gst.State.NULL)
        elif t == Gst.MessageType.ERROR:
            self._player.set_state(Gst.State.NULL)
            err, debug = message.parse_error()
            print(f'Error: {err}', debug)
