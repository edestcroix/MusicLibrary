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
        if self._need_seek():
            value = self._scale.get_value()
            self._last_position = value
            self._player.seek(value * TIME_DIVISOR)
            return True

        progress, duration = self._get_player_state()
        if duration != self._duration:
            # depending on when the duration is queried, the pipeline might return -1 if it
            # hasn't finished loading the track yet, so the abs() prevents range errors.
            self._scale.set_range(0, abs(duration))
            self._duration = duration
        self._update_widgets(progress)
        self._last_position = progress
        return True

    def _get_player_state(self):
        return (
            self._player.get_progress() / TIME_DIVISOR,
            self._player.get_duration() / TIME_DIVISOR,
        )

    # check if the player needs to seek to the current position
    # This is done by checking if the difference between the current position
    # and the last, rather than connecting to the scale's change-value signal
    # because that signal sends really inconsistent and sometimes negative values,
    # which causes the player to seek back to the start of the track.
    def _need_seek(self):
        return abs(self._last_position - self._scale.get_value()) > 1

    def _update_widgets(self, value):
        progress = self._format_time(value)
        self._scale.set_value(value)
        self._start_label.set_text(progress)

    def _format_time(self, time):
        return f'{int(time // 60)}:{int(time % 60):0>2}'
