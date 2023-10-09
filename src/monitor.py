from gi.repository import GLib

import threading
import time

TIME_DIVISOR = 1000000000
SLEEP_TIME = 0.1


# Class that manages the thread that updates the progress bar and time labels.
class ProgressMonitor:
    def __init__(self, player, scale, start_label, end_label):
        self._player = player
        self._scale = scale
        self._start_label = start_label
        self._end_label = end_label
        self._thread = None
        self._stop_event = threading.Event()

    def start_thread(self):
        # A monitor thread only needs to be started if one isn't already running.
        # If the user clicks play while an album is already playing, the thread
        # can be left running and carry over to the new album.
        if not self._thread:
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run, daemon=True)
            print('Starting progress monitor thread')
            self._thread.start()

    def stop_thread(self):
        if self._thread:
            print('Stopping progress monitor thread')
            self._stop_event.set()
            self._thread.join()
            self._thread = None

    def seek_event(self, _, __, value):
        self._player.seek(value * TIME_DIVISOR)

    def _run(self):
        while not self._stop_event.is_set():
            time.sleep(SLEEP_TIME)
            self._update_scale()
        self._update_widgets(0, '0:00')

    def _update_scale(self):
        if self._player.state == 'playing':
            duration = self._player.get_duration() / TIME_DIVISOR
            progress = self._player.get_progress() / TIME_DIVISOR
            time_str = self._format_time(progress)
            # Need to check this because when a track starts these
            # values are set to 0, which causes an exception in the Gtk.Scale
            if progress < duration:
                GLib.idle_add(self._scale.set_range, 0, duration)
            self._update_widgets(progress, time_str)

    def _update_widgets(self, value, progress):
        GLib.idle_add(self._scale.set_value, value)
        GLib.idle_add(self._start_label.set_text, progress)

    def _format_time(self, time):
        return f'{int(time // 60)}:{int(time % 60):0>2}'
