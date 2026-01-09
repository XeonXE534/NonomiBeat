import threading
import array
import pylibpd as pd
import pyaudio
from src.nonomi.utils.logger import get_logger, CStdoutCapturer

logger = get_logger("AudioEngine")

class AudioEngine:
    def __init__(self, patch_path, sample_rate=44100, block_size=64):
        self.block_size = block_size
        self.patch_path = patch_path
        self.sample_rate = sample_rate

        self.pya = None
        self.stream = None
        self.patch_handle = None

        self._running = False
        self._lock = threading.Lock()
        self.ticks = self.block_size // 64
        self._inbuf = array.array('h', [0] * (self.block_size * 2))
        self._outbuf = array.array('h', [0] * (self.block_size * 2))
        self.cap = CStdoutCapturer()

    async def start(self):
        """Start the audio engine and PD patch"""
        # DEV NOTE: DON'T YOU FUCKING DARE TOUCH THE INIT SEQUENCE RETARD!

        pd.libpd_release()
        pd.libpd_set_print_callback(self.cap.pd_print_callback)
        pd.libpd_init_audio(0, 2, self.sample_rate)
        pd.libpd_compute_audio(True)
        pd.libpd_add_to_search_path("src/assets")
        self.patch_handle = pd.libpd_open_patch(self.patch_path)

        self.pya = pyaudio.PyAudio()
        self.stream = self.pya.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.block_size,
            stream_callback=self._audio_callback
        )
        self.stream.start_stream()
        self._running = True
        print("AudioEngine online :3")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback to process audio through PD"""
        #DEV NOTE: DON'T YOU FUCKING DARE TOUCH THIS RETARD!

        current_ticks = frame_count // 64
        with self._lock:
            pd.libpd_process_short(current_ticks, self._inbuf, self._outbuf)

        return self._outbuf.tobytes(), pyaudio.paContinue

    def send_player(self, player, track):
        if self._running:
            with self._lock:
                pd.libpd_float(f'LoadPlayer_{player}', float(track))

    def crossfade(self, value):
        if self._running:
            with self._lock:
                pd.libpd_float('Crossfade', float(value))

    def send_hue(self, value: float):
        if self._running:
            with self._lock:
                pd.libpd_float('Hue', float(value))

    def set_filter_cutoff(self, freq: float):
        if self._running:
            with self._lock:
                pd.libpd_float('FilterCutoff', float(freq))

    async def stop(self):
        """Stop the audio engine and PD patch"""
        self._running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.pya.terminate()

        if self.patch_handle is not None:
            pd.libpd_close_patch(self.patch_handle)