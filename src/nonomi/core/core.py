from src.nonomi.utils.logger import get_logger
from src.nonomi.audio.audio import AudioEngine
from src.nonomi.input.cam import CameraInput

from tinytag import TinyTag
import asyncio
import random
import os

logger = get_logger("NonomiCore")

class NonomiBeat:
    def __init__(self, patch_path: str):
        self._track_metadata = _scan_assets()
        self._current_player = 1
        self.camera = CameraInput()
        self.audio = AudioEngine(patch_path=patch_path)
        self._running = False
        self._task = None

        self._blocks = {
            0: [0, 1, 2, 3, 4],  # Block 1
            1: [5, 6, 7, 8, 9]   # Block 2
        }
        self._current_block = 0
        self._track = 1
        self._last_track = None

    async def start(self):
        """Start all systems and main loop"""
        self._running = True

        logger.info("NonomiBeat started :3")
        print("NonomiBeat started :3")
        print(f"Using patch: {self.audio.patch_path}")

        await self.camera.start()
        await self.audio.start()
        await self._main_loop()


    async def stop(self):
        """Stop all systems"""
        self._running = False
        if self._task:
            await self._task

        await self.camera.stop()
        await self.audio.stop()

        logger.info("NonomiBeat stopped :3")

    async def _main_loop(self):
        """Main processing loop"""
        try:
            """
                        # 4. Calculate Smart Sleep
                        # Fallback to 120s if metadata fails for some reason
                        duration = self._track_metadata.get(self._track, 120)
            
                        if duration < 155:
                            # Play the whole track (minus crossfade buffer)
                            sleep_time = max(5, duration - 5)
                            logger.info(f"Short track detected. Playing full {duration:.1f}s.")
                        else:
                            # Long track: Switch between 2 mins and the end
                            sleep_time = random.uniform(120, duration - 10)
                            logger.info(f"Long track detected. Cutting at {sleep_time:.1f}s / {duration:.1f}s.")
            
                        # 5. The Big Wait
                        # Note: During this sleep, your Filter/Hue won't update.
                        # If you want FX to stay live, we need a nested loop.
                        await asyncio.sleep(sleep_time)
            
                except Exception as e:
                    logger.error(f"Main loop error: {e} :(")
                    await self.stop()"""
            while self._running:
                brightness, hue = self.camera.get_values()
                cutoff = self._brightness_to_filter(brightness)
                self.audio.set_filter_cutoff(cutoff)
                self.audio.send_hue(hue)

                self._track = self._pick_random_from_block(self._current_block)
                active_player = 1 if self._current_player == 0 else 0

                self.audio.send_player(active_player, self._track)
                self.audio.crossfade(active_player)
                self._current_player = active_player

                duration = self._track_metadata.get(self._track, 120)
                if duration < 155:
                    sleep_time = max(5, duration - 5)
                    logger.info(f"Short track detected. Playing full {duration:.1f}s :3")

                else:
                    sleep_time = random.uniform(120, duration - 10)
                    logger.info(f"Long track detected. Cutting at {sleep_time:.1f}s / {duration:.1f}s :3")

                await asyncio.sleep(sleep_time)

                await asyncio.sleep(0.5) # uhh? I have no idea why this is here, but I guess we keep it...? doesn't add much delay anyway

        except Exception as e:
            logger.error(f"Main loop error: {e} :(")
            await self.stop()

    def _pick_random_from_block(self, block_id) -> int:
        pool = self._blocks.get(block_id, self._blocks[0])
        if len(pool) <= 1:
            return pool[0]
        new_track = random.choice(pool)

        while new_track == self._last_track and len(pool) > 1:
            new_track = random.choice(pool)
        return new_track

    def _scan_assets(self):
        self._track_metadata = {}

        for block_id, track_indices in self._blocks.items():
            for index in track_indices:
                path = f"src/assets/track_{index:02d}.wav"

                if os.path.exists(path):
                    tag = TinyTag.get(path)
                    self._track_metadata[index] = tag.duration

        return self._track_metadata if self._track_metadata else None

    @staticmethod
    def _brightness_to_filter(brightness: float) -> float:
        """Map brightness to lowpass filter cutoff"""
        min_freq = 500   # Hz
        max_freq = 8000  # Hz
        val = min_freq + (brightness * (max_freq - min_freq)) # I have no idea why I use this formula but it works so ¯\_(ツ)_/¯
        val = round(val, 1)
        return val
