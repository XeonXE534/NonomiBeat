import threading
import array
import pylibpd as pd
import pyaudio
from ..utils.logger import get_logger

logger = get_logger("AudioEngine")

class AudioEngine:
    def __init__(self, patch_path, sample_rate=44100, block_size=64):
        self.stream = None
        self.pya = None
        self.patch_handle = None
        self.block_size = block_size # MUST be a multiple of 64
        self.patch_path = patch_path
        self.sample_rate = sample_rate
        self._lock = threading.Lock()
        self._running = False

        # Pre-allocate exactly for stereo (2 channels)
        # 64 samples * 2 channels * ticks
        self.ticks = self.block_size // 64
        self._inbuf = array.array('h', [0] * (self.block_size * 2))
        self._outbuf = array.array('h', [0] * (self.block_size * 2))

    async def start(self):
        # HARD RESET
        pd.libpd_release()

        # Init must happen BEFORE opening the patch
        pd.libpd_init_audio(0, 2, self.sample_rate)
        pd.libpd_compute_audio(True)

        import os
        patch_dir = os.path.dirname(os.path.abspath(self.patch_path))
        patch_file = os.path.basename(self.patch_path)

        self.patch_handle = pd.libpd_open_patch(patch_file, patch_dir)
        if not self.patch_handle:
            print("FAILED TO OPEN PATCH (X_X)")
            return

        self.pya = pyaudio.PyAudio()
        self.stream = self.pya.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=self.sample_rate,
            output=True,
            # Use the same block size everywhere
            frames_per_buffer=self.block_size,
            stream_callback=self._audio_callback
        )
        self.stream.start_stream()
        self._running = True
        info = self.pya.get_default_output_device_info()
        print(f"!!! USING DEVICE: {info['name']} at {self.sample_rate}Hz")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        # Calculate ticks based on what PyAudio actually gives us
        current_ticks = frame_count // 64

        with self._lock:
            # If current_ticks doesn't match our buffer, we have a problem
            pd.libpd_process_short(current_ticks, self._inbuf, self._outbuf)

        return self._outbuf.tobytes(), pyaudio.paContinue

    def send_brightness(self, value):
        if self._running:
            with self._lock:
                pd.libpd_float('brightness', float(value))

    def send_hue(self, value: float):
        if self._running:
            with self._lock:
                pd.libpd_float('hue', float(value))

    def set_filter_cutoff(self, freq: float):
        if self._running:
            with self._lock:
                pd.libpd_float('filter_cutoff', 2000.0)

    def play_track(self, track_id: int):
        """Tell PD which track to play (0-9)"""
        if self._running:
            with self._lock:
                pd.libpd_float('track', float(track_id))
                logger.debug(f"→ track: {track_id}")

    async def stop(self):
        self._running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.pya.terminate()

        if self.patch_handle is not None:
            pd.libpd_close_patch(self.patch_handle)