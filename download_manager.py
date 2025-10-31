"""
Download Manager
Handles queuing, downloading, and uploading episodes
"""

import os
import asyncio
import logging
from typing import Dict, Any
from pathlib import Path

from api_handler import api_handler
from config import config

logger = logging.getLogger(__name__)

class DownloadManager:
    """Manages download queue and operations"""

    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.active_downloads: Dict[int, Dict[str, Any]] = {}

    async def add_to_queue(self, user_id: int, episode: Dict[str, Any]):
        """Add episode to download queue"""
        await self.queue.put({
            "user_id": user_id,
            "episode": episode,
            "status": "queued"
        })
        logger.info(f"Episode queued for user {user_id}: {episode.get('title')}")

    async def process_queue(self, bot):
        """Process download queue"""
        logger.info("Download queue processor started")

        while True:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=30)
                await self._process_item(bot, item)
                self.queue.task_done()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                await asyncio.sleep(5)

    async def _process_item(self, bot, item: Dict[str, Any]):
        """Process a single download item"""

        user_id = item["user_id"]
        episode = item["episode"]
        episode_id = episode.get("id", "unknown")
        episode_title = episode.get("title", "Unknown Episode")

        status_msg = None

        try:
            # Send initial status
            status_msg = await bot.send_message(
                user_id,
                f"📥 **Downloading:** {episode_title}\n\n⏳ Getting stream URL..."
            )

            # Get stream URL
            stream_url = await api_handler.get_stream_url(episode_id)

            if not stream_url:
                await status_msg.edit_text(
                    f"❌ **Failed:** Could not get stream URL\n\n"
                    f"Episode: {episode_title}"
                )
                logger.warning(f"No stream URL for episode {episode_id}")
                return

            # Create download directory
            Path(config.DOWNLOAD_PATH).mkdir(parents=True, exist_ok=True)
            filepath = os.path.join(config.DOWNLOAD_PATH, f"{episode_id}.mp3")

            # Setup progress callback
            last_update = [0]

            async def download_progress(percent, downloaded, total):
                current_time = asyncio.get_event_loop().time()
                if current_time - last_update[0] > 2:
                    try:
                        size_mb = total / (1024 * 1024)
                        await status_msg.edit_text(
                            f"📥 **Downloading:** {episode_title}\n\n"
                            f"Progress: {percent:.1f}%\n"
                            f"Size: {size_mb:.2f} MB"
                        )
                    except:
                        pass
                    last_update[0] = current_time

            # Download episode
            success = await api_handler.download_file(
                stream_url,
                filepath,
                download_progress
            )

            if not success:
                await status_msg.edit_text(
                    f"❌ **Download Failed**\n\n"
                    f"Episode: {episode_title}\n"
                    f"Please try again later"
                )
                return

            # Upload to Telegram
            await status_msg.edit_text(
                f"📤 **Uploading to Telegram**\n\n"
                f"{episode_title}..."
            )

            try:
                await bot.send_audio(
                    chat_id=user_id,
                    audio=filepath,
                    title=episode_title,
                    performer="Pocket FM",
                    duration=episode.get("duration", 0)
                )

                await status_msg.delete()

                await bot.send_message(
                    user_id,
                    f"✅ **Download Complete!**\n\n"
                    f"**{episode_title}** has been downloaded and uploaded.\n"
                    f"You can now listen to it!"
                )

                logger.info(f"Successfully processed episode {episode_id} for user {user_id}")

            except Exception as e:
                logger.error(f"Upload error: {e}")
                await status_msg.edit_text(
                    f"⚠️ **Download complete but upload failed**\n\n"
                    f"File saved locally: {filepath}"
                )

            finally:
                # Cleanup
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        logger.debug(f"Cleaned up: {filepath}")
                    except:
                        pass

        except Exception as e:
            logger.error(f"Error processing episode {episode_id}: {e}")
            if status_msg:
                try:
                    await status_msg.edit_text(
                        f"❌ **Error**\n\n{str(e)[:200]}"
                    )
                except:
                    pass

# Global instance
download_manager = DownloadManager()
