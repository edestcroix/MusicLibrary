from gi.repository import GLib

TIME_DIVISOR = 1000000000
TIMEOUT = 100

# Class responsible for monitoring the player's progress and updating the
# progress bar and position label. Also handles seek events. Might roll this
# into a widget subclass for the progress bar later.
class ProgressMonitor:
    def __init__(self, player, scale, start_label, end_label):
        self._player = player
        self._scale = scale
        self._start_label = start_label
        self._end_label = end_label
        self._last_position = 0
        self._duration = 0
        self._active = False

    def start(self):
        if self._active:
            return
        self._active = True
        GLib.timeout_add(TIMEOUT, self._check_state)

    def _check_state(self):
        if self._player.state != 'stopped':
            return self._update_state()
        self._update_widgets(0)
        self._active = False
        return False

    def _update_state(self):
        position, duration = self._get_player_state()
        # if durations don't match, the track has changed.
        if duration != self._duration:
            # depending on when the duration is queried, the pipeline might return -1 if it
            # hasn't finished loading the track yet, so the abs() prevents range errors.
            self._scale.set_range(0, abs(duration))
            self._duration = duration
            self._last_position = 0
            self._update_widgets(0)
        else:
            # otherwise, check for a seek
            value = self._scale.get_value()
            if abs(value - self._last_position) > 1:
                self._player.seek(value * TIME_DIVISOR)
            else:
                self._update_widgets(position)
            self._last_position = value
        return True

    def _get_player_state(self):
        return (
            self._player.get_progress() / TIME_DIVISOR,
            self._player.get_duration() / TIME_DIVISOR,
        )

    def _update_widgets(self, value):
        progress = self._format_time(value)
        self._scale.set_value(value)
        self._start_label.set_text(progress)

    def _format_time(self, time):
        return f'{int(time // 60)}:{int(time % 60):0>2}'
