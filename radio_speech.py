"""
Speech generation and volume control for the radio orchestrator.

Wraps the speech engines, afplay for output, and Spotify's volume endpoint for
ducking. Kept separate from the loop so that the text-to-speech engine can be
replaced without touching the scheduling logic, which is exactly what happened
when Kokoro replaced Piper as the main engine.

Two engines are supported and chosen by the voice name alone. Piper voices are
named like en_GB-alan-medium and always contain a hyphen. Kokoro voices are
named like bm_george and never do. Piper stays as the fallback, because it is
fast, small and well proven on modest hardware.

p1_talk_once.py deliberately still carries its own copy of this logic. It is the
standing single-shot reference for the mechanism, and is left alone so that a
change here cannot break the script used to verify the setup.
"""

import os
import re
import subprocess
import sys
import threading
import time
import wave

import normalise

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(HERE, "audio")
VOICE_DIR = os.path.join(HERE, "voices")

KOKORO_DIR = os.path.join(VOICE_DIR, "kokoro")
KOKORO_MODEL = os.path.join(KOKORO_DIR, "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(KOKORO_DIR, "voices-v1.0.bin")

# Delivery speed per Kokoro voice, where 1.0 is the model's own. The newsreader
# runs slightly slower, chosen by ear over three alternatives, because a
# bulletin read at conversational speed sounds hurried.
KOKORO_SPEED = {"bf_emma": 0.92}

# Silence placed after each kind of break, in milliseconds. Left to itself the
# model gives every punctuation mark the same pause of about a fifth of a
# second, measured, so a comic beat marked with an ellipsis gets no more room
# than a comma. That uniformity was the loudest thing making it sound
# generated. Commas are deliberately not split on, because speaking each
# clause separately costs the rise and fall across a sentence.
PAUSE_MS = {"...": 550, ".": 380, "?": 380, "!": 380}

# A sentence end or an ellipsis, followed by space or the end of the text. The
# lookahead is what stops a decimal such as 3.5 being treated as a full stop.
_PIECE = re.compile(r".+?(?:\.\.\.|[.?!]|$)(?=\s|$)")

_kokoro = None
_kokoro_lock = threading.Lock()

# Each fade step is an HTTP request to Spotify, so the cost is dominated by
# round-trip latency rather than the sleep. Both fades must fit inside the break
# window or the volume is restored after the next track has started.
FADE_STEPS = 6
FADE_SLEEP = 0.08
FADE_MS = 1200

# Quiet track left after the presenter finishes and the volume is back up.
TAIL_PADDING_MS = 1500


def break_window_ms(clip_ms):
    """Total track time a break needs: fade down, speech, fade up, then tail."""
    return clip_ms + (2 * FADE_MS) + TAIL_PADDING_MS


def _python_bin():
    venv_python = os.path.join(HERE, ".venv", "bin", "python")
    return venv_python if os.path.exists(venv_python) else sys.executable


def _piper_bin():
    piper = os.path.join(HERE, ".venv", "bin", "piper")
    return piper if os.path.exists(piper) else "piper"


def is_kokoro(voice):
    """True for a Kokoro voice name, false for a Piper one."""
    return "-" not in voice


def ensure_voice(voice):
    """Make sure a voice can be used, downloading it if it is a Piper voice.

    Kokoro's model and voice pack are downloaded once by hand, so for a Kokoro
    voice this only checks they are present and says clearly if they are not.
    Raises RuntimeError when the voice cannot be used, which the loop treats as
    a reason to fall back rather than to stop.
    """
    if is_kokoro(voice):
        for path in (KOKORO_MODEL, KOKORO_VOICES):
            if not os.path.exists(path):
                raise RuntimeError("Kokoro file missing: {}".format(path))
        if voice not in _kokoro_engine().get_voices():
            raise RuntimeError("no Kokoro voice called {}".format(voice))
        return
    os.makedirs(VOICE_DIR, exist_ok=True)
    if os.path.exists(os.path.join(VOICE_DIR, voice + ".onnx")):
        return
    print("  downloading voice {}".format(voice))
    result = subprocess.run(
        [_python_bin(), "-m", "piper.download_voices", voice,
         "--download-dir", VOICE_DIR],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "could not download voice {}: {}".format(
                voice, result.stderr.decode("utf-8", "replace")
            )
        )


def _kokoro_engine():
    """The loaded Kokoro model, created on first use and then kept.

    Loading takes a couple of seconds and several hundred megabytes, so it
    happens once rather than per clip. The import is deferred so that a
    Piper only setup does not need Kokoro installed at all.
    """
    global _kokoro
    with _kokoro_lock:
        if _kokoro is None:
            from kokoro_onnx import Kokoro
            _kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
    return _kokoro


def _pieces(text):
    """Split text at sentence ends and ellipses, keeping each mark on its piece."""
    pieces = [p.strip() for p in _PIECE.findall(text.strip()) if p.strip()]
    return pieces or [text.strip()]


def _trim(samples, rate, floor=0.01):
    """Drop a clip's own leading and trailing silence, keeping a short margin.

    Without this the model's silence and the chosen pause add together, and
    the pauses come out longer and less even than intended.
    """
    import numpy as np
    loud = np.where(np.abs(samples) > floor)[0]
    if not len(loud):
        return samples
    margin = int(rate * 0.02)
    return samples[max(0, loud[0] - margin): loud[-1] + margin]


def _kokoro_render(text, voice, path):
    """Speak text with Kokoro, piece by piece, with pauses set by punctuation."""
    import numpy as np
    engine = _kokoro_engine()
    speed = KOKORO_SPEED.get(voice, 1.0)
    rate = 24000
    chunks = []
    for piece in _pieces(text):
        samples, rate = engine.create(piece, voice=voice, speed=speed, lang="en-gb")
        chunks.append(_trim(samples, rate))
        mark = "..." if piece.endswith("...") else piece[-1]
        pause = PAUSE_MS.get(mark, 150)
        chunks.append(np.zeros(int(rate * pause / 1000), dtype=np.float32))
    audio = np.concatenate(chunks[:-1])

    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())


def synthesise(text, voice, name):
    """Render text to a wav file. Returns (path, duration_ms).

    The name is used for the filename so that a clip being generated in the
    background cannot overwrite one that is waiting to air.
    """
    os.makedirs(AUDIO_DIR, exist_ok=True)
    path = os.path.join(AUDIO_DIR, "{}.wav".format(name))

    # Applied here rather than where the text is written, because this is the
    # one point every spoken line passes through, bulletins and patter alike.
    text = normalise.amounts(text)

    if is_kokoro(voice):
        _kokoro_render(text, voice, path)
        with wave.open(path, "rb") as handle:
            duration_ms = int(1000 * handle.getnframes() / handle.getframerate())
        return path, duration_ms

    ensure_voice(voice)

    command = [
        _piper_bin(),
        "--model", voice,
        "--data-dir", VOICE_DIR,
        "--output-file", path,
    ]
    result = subprocess.run(command, input=text.encode("utf-8"), capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            "piper failed: {}".format(result.stderr.decode("utf-8", "replace"))
        )

    with wave.open(path, "rb") as handle:
        duration_ms = int(1000 * handle.getnframes() / handle.getframerate())
    return path, duration_ms


def play(path):
    """Play a clip through the default output device and block until it ends."""
    subprocess.run(["afplay", path], check=True)


def set_volume(sp, level):
    """Set Spotify volume, returning False if the device refuses the request."""
    try:
        sp.volume(max(0, min(100, int(level))))
        return True
    except Exception:
        return False


def fade(sp, start, end):
    """Ramp Spotify's volume. Returns elapsed milliseconds, or None if refused."""
    started = time.time()
    for step in range(1, FADE_STEPS + 1):
        level = start + (end - start) * step / FADE_STEPS
        if not set_volume(sp, level):
            return None
        time.sleep(FADE_SLEEP)
    return int(1000 * (time.time() - started))
