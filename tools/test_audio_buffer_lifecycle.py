"""Smoke coverage for a long-lived QAudioBufferOutput during player resets."""

import os
import struct
import sys
import tempfile
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioBufferOutput, QAudioOutput, QMediaPlayer, QVideoSink
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid


app = QApplication.instance() or QApplication(["audio-buffer-lifecycle-test"])
owner = QCoreApplication.instance()
audio_tap = QAudioBufferOutput(owner)
audio_output = QAudioOutput(owner)
player = QMediaPlayer(owner)
sink = QVideoSink(owner)
player.setAudioOutput(audio_output)
player.setVideoSink(sink)
player.setAudioBufferOutput(audio_tap)
audio_tap.audioBufferReceived.connect(lambda _buffer: None)

state = {"resets": 0}


def reset_after_status_callback():
    player.stop()
    player.setSource(QUrl())
    assert isValid(audio_tap), "long-lived audio tap was destroyed during player replacement"
    assert player.audioBufferOutput() is audio_tap
    state["resets"] += 1
    if state["resets"] < 100:
        QTimer.singleShot(0, reset_after_status_callback)
    else:
        app.quit()


# Player reset is deferred to the next event-loop turn, matching the
# EndOfMedia/error callback handoff used by MediaWave.
QTimer.singleShot(0, reset_after_status_callback)
reset_watchdog = QTimer()
reset_watchdog.setSingleShot(True)
reset_watchdog.timeout.connect(app.quit)
reset_watchdog.start(5000)
app.exec()
reset_watchdog.stop()
assert state["resets"] == 100

# Exercise real EndOfMedia delivery with diagnostics attached. The same player
# and audio tap are reset on the next event-loop turn after the callback exits.
with tempfile.TemporaryDirectory(prefix="mediawave-audio-lifecycle-") as temp_dir:
    wav_path = os.path.join(temp_dir, "short.wav")
    sample_rate = 8000
    with wave.open(wav_path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(struct.pack("<h", 0) * int(sample_rate * 0.15))

    end_state = {"count": 0, "waiting_to_start": True, "reset_complete": False, "timed_out": False}

    def start_short_media():
        end_state["waiting_to_start"] = True
        player.stop()
        player.setSource(QUrl())
        player.setSource(QUrl.fromLocalFile(wav_path))

    def on_status(status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and end_state["waiting_to_start"]:
            end_state["waiting_to_start"] = False
            player.play()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            end_state["count"] += 1
            QTimer.singleShot(0, reset_after_end)

    def reset_after_end():
        player.stop()
        player.setSource(QUrl())
        assert player.audioBufferOutput() is audio_tap
        assert isValid(audio_tap)
        end_state["reset_complete"] = True
        app.quit()

    player.mediaStatusChanged.connect(on_status)
    QTimer.singleShot(0, start_short_media)

    def timeout():
        end_state["timed_out"] = True
        app.quit()

    end_watchdog = QTimer()
    end_watchdog.setSingleShot(True)
    end_watchdog.timeout.connect(timeout)
    end_watchdog.start(5000)
    app.exec()
    end_watchdog.stop()
    player.mediaStatusChanged.disconnect(on_status)
    assert not end_state["timed_out"], "EndOfMedia lifecycle test timed out"
    assert end_state["count"] == 1
    assert end_state["reset_complete"]
    assert player.audioBufferOutput() is audio_tap
    assert isValid(audio_tap)

player.setAudioBufferOutput(None)
player.setVideoSink(None)
player.setAudioOutput(None)
player.deleteLater()
sink.deleteLater()
app.processEvents()
assert isValid(audio_tap), "detached audio tap should remain valid until owner shutdown"

print("QAudioBufferOutput lifecycle smoke test passed.")
