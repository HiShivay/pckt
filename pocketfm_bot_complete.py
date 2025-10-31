"""
Pocket FM Content Downloader Bot
A comprehensive Telegram bot for downloading Pocket FM audio series with proper episode selection,
download management, and upload functionality.

Features:
- Download free and premium content
- Episode selection (individual or bulk download)
- Progress tracking
- Upload to Telegram
- Extract unreleased episodes from API
- Proper error handling and logging
"""

import os
import sys
import asyncio
import logging
import json
import aiohttp
import aiofiles
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    CallbackQuery
)
from pyrogram.enums import ParseMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pocketfm_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
class Config:
    """Bot configuration"""
    # Telegram Bot Credentials
    API_ID = "YOUR_API_ID"  # Get from https://my.telegram.org
    API_HASH = "YOUR_API_HASH"  # Get from https://my.telegram.org
    BOT_TOKEN = "YOUR_BOT_TOKEN"  # Get from @BotFather

    # Owner/Admin User IDs (for restricted commands)
    OWNER_IDS = [123456789]  # Add your Telegram user ID

    # Download settings
    DOWNLOAD_PATH = "downloads"
    MAX_CONCURRENT_DOWNLOADS = 3
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks

    # Pocket FM API Configuration
    # Note: These are example endpoints - actual endpoints need to be reverse-engineered
    POCKETFM_BASE_URL = "https://api.pocketfm.com"  # Base API URL
    POCKETFM_API_VERSION = "v1"

    # API Headers (to mimic official app)
    DEFAULT_HEADERS = {
        "User-Agent": "PocketFM/8.12.3 (Android 13; Mobile)",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Client-Version": "8.12.3",
        "X-Platform": "android"
    }

# ==================== HELPER CLASSES ====================
class PocketFMAPI:
    """Pocket FM API Handler"""

    def __init__(self):
        self.base_url = Config.POCKETFM_BASE_URL
        self.headers = Config.DEFAULT_HEADERS.copy()
        self.session: Optional[aiohttp.ClientSession] = None

    async def init_session(self):
        """Initialize aiohttp session"""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()

    async def search_series(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for audio series by query

        Args:
            query: Search term

        Returns:
            List of series matching the query
        """
        await self.init_session()

        try:
            # Example endpoint - needs to be reverse-engineered
            url = f"{self.base_url}/api/{Config.POCKETFM_API_VERSION}/search"
            params = {
                "q": query,
                "type": "series",
                "limit": 10
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("results", [])
                else:
                    logger.error(f"Search failed: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error searching series: {e}")
            return []

    async def get_series_details(self, series_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a series

        Args:
            series_id: Series ID

        Returns:
            Series details including episodes
        """
        await self.init_session()

        try:
            url = f"{self.base_url}/api/{Config.POCKETFM_API_VERSION}/series/{series_id}"

            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get series details: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting series details: {e}")
            return None

    async def get_episodes(self, series_id: str, include_unreleased: bool = False) -> List[Dict[str, Any]]:
        """
        Get all episodes for a series

        Args:
            series_id: Series ID
            include_unreleased: Include unreleased episodes if available

        Returns:
            List of episodes
        """
        await self.init_session()

        try:
            url = f"{self.base_url}/api/{Config.POCKETFM_API_VERSION}/series/{series_id}/episodes"
            params = {}

            if include_unreleased:
                params["include_unreleased"] = "true"

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("episodes", [])
                else:
                    logger.error(f"Failed to get episodes: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error getting episodes: {e}")
            return []

    async def get_episode_download_url(self, episode_id: str, quality: str = "high") -> Optional[str]:
        """
        Get download URL for an episode

        Args:
            episode_id: Episode ID
            quality: Audio quality (low, medium, high)

        Returns:
            Download URL or None
        """
        await self.init_session()

        try:
            url = f"{self.base_url}/api/{Config.POCKETFM_API_VERSION}/episodes/{episode_id}/stream"
            params = {"quality": quality}

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("url")
                else:
                    logger.error(f"Failed to get download URL: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting download URL: {e}")
            return None

    async def download_episode(self, download_url: str, filepath: str, progress_callback=None) -> bool:
        """
        Download an episode to file

        Args:
            download_url: URL to download from
            filepath: Path to save file
            progress_callback: Optional callback for progress updates

        Returns:
            True if successful, False otherwise
        """
        await self.init_session()

        try:
            async with self.session.get(download_url) as response:
                if response.status == 200:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    async with aiofiles.open(filepath, 'wb') as f:
                        async for chunk in response.content.iter_chunked(Config.CHUNK_SIZE):
                            await f.write(chunk)
                            downloaded += len(chunk)

                            if progress_callback and total_size > 0:
                                progress = (downloaded / total_size) * 100
                                await progress_callback(progress, downloaded, total_size)

                    return True
                else:
                    logger.error(f"Download failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error downloading episode: {e}")
            return False

class DownloadManager:
    """Manages download queue and progress"""

    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.active_downloads: Dict[int, Dict[str, Any]] = {}
        self.api = PocketFMAPI()

    async def add_to_queue(self, user_id: int, episode: Dict[str, Any]):
        """Add episode to download queue"""
        await self.queue.put({
            "user_id": user_id,
            "episode": episode,
            "timestamp": datetime.now()
        })

    async def process_queue(self, bot: Client):
        """Process download queue"""
        while True:
            try:
                item = await self.queue.get()
                await self._download_and_upload(bot, item)
                self.queue.task_done()
            except Exception as e:
                logger.error(f"Error processing queue: {e}")
                await asyncio.sleep(5)

    async def _download_and_upload(self, bot: Client, item: Dict[str, Any]):
        """Download episode and upload to Telegram"""
        user_id = item["user_id"]
        episode = item["episode"]
        episode_id = episode["id"]
        episode_title = episode["title"]

        try:
            # Update user about download start
            status_msg = await bot.send_message(
                user_id,
                f"📥 **Downloading:** {episode_title}\n\n⏳ Starting download..."
            )

            # Get download URL
            download_url = await self.api.get_episode_download_url(episode_id)
            if not download_url:
                await status_msg.edit_text("❌ Failed to get download URL")
                return

            # Create download directory
            Path(Config.DOWNLOAD_PATH).mkdir(parents=True, exist_ok=True)
            filepath = os.path.join(Config.DOWNLOAD_PATH, f"{episode_id}.mp3")

            # Progress callback
            last_update = [0]
            async def progress(percent, downloaded, total):
                current_time = asyncio.get_event_loop().time()
                if current_time - last_update[0] > 2:  # Update every 2 seconds
                    await status_msg.edit_text(
                        f"📥 **Downloading:** {episode_title}\n\n"
                        f"Progress: {percent:.1f}%\n"
                        f"Downloaded: {downloaded/(1024*1024):.2f} MB / {total/(1024*1024):.2f} MB"
                    )
                    last_update[0] = current_time

            # Download
            success = await self.api.download_episode(download_url, filepath, progress)

            if not success:
                await status_msg.edit_text("❌ Download failed")
                return

            # Upload to Telegram
            await status_msg.edit_text(
                f"📥 **Downloaded:** {episode_title}\n\n"
                f"📤 Uploading to Telegram..."
            )

            await bot.send_audio(
                chat_id=user_id,
                audio=filepath,
                title=episode_title,
                caption=f"🎧 **{episode_title}**\n\nEpisode ID: {episode_id}",
                progress=self._upload_progress,
                progress_args=(status_msg, episode_title)
            )

            # Cleanup
            await status_msg.delete()
            os.remove(filepath)

            logger.info(f"Successfully processed episode {episode_id} for user {user_id}")

        except Exception as e:
            logger.error(f"Error in download/upload: {e}")
            try:
                await bot.send_message(user_id, f"❌ Error: {str(e)}")
            except:
                pass

    @staticmethod
    async def _upload_progress(current, total, status_msg, episode_title):
        """Upload progress callback"""
        try:
            percent = (current / total) * 100
            await status_msg.edit_text(
                f"📤 **Uploading:** {episode_title}\n\n"
                f"Progress: {percent:.1f}%\n"
                f"Uploaded: {current/(1024*1024):.2f} MB / {total/(1024*1024):.2f} MB"
            )
        except:
            pass

# ==================== BOT INSTANCE ====================
app = Client(
    "pocketfm_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# Global instances
download_manager = DownloadManager()
user_data: Dict[int, Dict[str, Any]] = {}

# ==================== DECORATORS ====================
def owner_only(func):
    """Decorator to restrict command to owners only"""
    async def wrapper(client, message):
        if message.from_user.id not in Config.OWNER_IDS:
            await message.reply_text("⛔ This command is restricted to bot owners only.")
            return
        return await func(client, message)
    return wrapper

# ==================== COMMAND HANDLERS ====================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Start command handler"""
    welcome_text = (
        "🎧 **Welcome to Pocket FM Downloader Bot!**\n\n"
        "This bot helps you download Pocket FM audio series.\n\n"
        "**Available Commands:**\n"
        "• /search <query> - Search for series\n"
        "• /help - Show help message\n"
        "• /about - About this bot\n\n"
        "**How to use:**\n"
        "1. Use /search to find a series\n"
        "2. Select the series you want\n"
        "3. Choose episodes to download\n"
        "4. Sit back and relax! 🍿"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Help", callback_data="help"),
         InlineKeyboardButton("ℹ️ About", callback_data="about")],
        [InlineKeyboardButton("🔍 Start Searching", switch_inline_query_current_chat="")]
    ])

    await message.reply_text(welcome_text, reply_markup=keyboard)

@app.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    """Help command handler"""
    help_text = (
        "📚 **Help & Commands**\n\n"
        "**Basic Commands:**\n"
        "/start - Start the bot\n"
        "/search <query> - Search for series\n"
        "/help - Show this help message\n"
        "/about - About this bot\n\n"
        "**Features:**\n"
        "✅ Download free and premium content\n"
        "✅ Select specific episodes or download all\n"
        "✅ Access unreleased episodes (if available)\n"
        "✅ Progress tracking during download\n"
        "✅ Direct upload to Telegram\n\n"
        "**Tips:**\n"
        "• Be specific with search queries for better results\n"
        "• Large downloads may take time, please be patient\n"
        "• You can queue multiple episodes\n\n"
        "For issues, contact the bot owner."
    )

    await message.reply_text(help_text)

@app.on_message(filters.command("about") & filters.private)
async def about_command(client: Client, message: Message):
    """About command handler"""
    about_text = (
        "ℹ️ **About Pocket FM Downloader Bot**\n\n"
        "**Version:** 1.0.0\n"
        "**Framework:** Pyrogram\n"
        "**Language:** Python 3.9+\n\n"
        "This bot helps you download and manage Pocket FM audio content "
        "with an easy-to-use interface.\n\n"
        "**Features:**\n"
        "• Advanced search functionality\n"
        "• Episode selection system\n"
        "• Queue management\n"
        "• Progress tracking\n"
        "• Automatic upload to Telegram\n\n"
        "**Developer:** @YourUsername\n"
        "**Support:** @YourSupportChannel"
    )

    await message.reply_text(about_text)

@app.on_message(filters.command("search") & filters.private)
async def search_command(client: Client, message: Message):
    """Search command handler"""
    # Extract search query
    query = message.text.split(maxsplit=1)

    if len(query) < 2:
        await message.reply_text(
            "❓ **Usage:** /search <series name>\n\n"
            "**Example:** /search saving nora"
        )
        return

    search_query = query[1]
    status_msg = await message.reply_text("🔍 Searching...")

    try:
        # Search for series
        results = await download_manager.api.search_series(search_query)

        if not results:
            await status_msg.edit_text("❌ No results found. Try a different search query.")
            return

        # Store results in user data
        user_data[message.from_user.id] = {
            "search_results": results,
            "last_search": search_query
        }

        # Create keyboard with results
        keyboard = []
        for idx, series in enumerate(results[:10]):  # Limit to 10 results
            series_title = series.get("title", "Unknown")
            series_id = series.get("id")
            keyboard.append([
                InlineKeyboardButton(
                    f"📚 {series_title}",
                    callback_data=f"series_{series_id}"
                )
            ])

        await status_msg.edit_text(
            f"🔍 **Search Results for:** {search_query}\n\n"
            f"Found {len(results)} series. Select one:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error in search: {e}")
        await status_msg.edit_text(f"❌ Error during search: {str(e)}")

@app.on_callback_query(filters.regex(r"^series_"))
async def series_callback(client: Client, callback: CallbackQuery):
    """Handle series selection"""
    series_id = callback.data.split("_")[1]

    await callback.message.edit_text("⏳ Loading series details...")

    try:
        # Get series details
        series_details = await download_manager.api.get_series_details(series_id)

        if not series_details:
            await callback.message.edit_text("❌ Failed to load series details.")
            return

        series_title = series_details.get("title", "Unknown")
        series_desc = series_details.get("description", "No description")
        total_episodes = series_details.get("total_episodes", 0)

        # Store in user data
        if callback.from_user.id not in user_data:
            user_data[callback.from_user.id] = {}
        user_data[callback.from_user.id]["current_series"] = series_details
        user_data[callback.from_user.id]["series_id"] = series_id

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 View Episodes", callback_data=f"episodes_{series_id}")],
            [InlineKeyboardButton("⬇️ Download All Episodes", callback_data=f"download_all_{series_id}")],
            [InlineKeyboardButton("🔓 Include Unreleased", callback_data=f"unreleased_{series_id}")],
            [InlineKeyboardButton("« Back to Search", callback_data="back_search")]
        ])

        text = (
            f"📚 **{series_title}**\n\n"
            f"**Description:** {series_desc[:200]}...\n\n"
            f"**Total Episodes:** {total_episodes}\n\n"
            f"What would you like to do?"
        )

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error in series callback: {e}")
        await callback.message.edit_text(f"❌ Error: {str(e)}")

@app.on_callback_query(filters.regex(r"^episodes_"))
async def episodes_callback(client: Client, callback: CallbackQuery):
    """Handle episodes list view"""
    series_id = callback.data.split("_")[1]

    await callback.message.edit_text("⏳ Loading episodes...")

    try:
        # Get episodes
        episodes = await download_manager.api.get_episodes(series_id, include_unreleased=False)

        if not episodes:
            await callback.message.edit_text("❌ No episodes found.")
            return

        # Store in user data
        user_data[callback.from_user.id]["episodes"] = episodes

        # Create episode selection keyboard (paginated)
        page = 0
        per_page = 10
        start = page * per_page
        end = start + per_page

        keyboard = []
        for episode in episodes[start:end]:
            ep_title = episode.get("title", "Unknown")
            ep_id = episode.get("id")
            ep_num = episode.get("episode_number", "?")
            keyboard.append([
                InlineKeyboardButton(
                    f"Ep {ep_num}: {ep_title[:40]}",
                    callback_data=f"ep_{ep_id}"
                )
            ])

        # Navigation buttons
        nav_buttons = []
        if end < len(episodes):
            nav_buttons.append(InlineKeyboardButton("Next »", callback_data=f"ep_page_{series_id}_1"))
        nav_buttons.append(InlineKeyboardButton("« Back", callback_data=f"series_{series_id}"))
        keyboard.append(nav_buttons)

        await callback.message.edit_text(
            f"📋 **Episodes** (Page 1/{(len(episodes)-1)//per_page + 1})\n\n"
            f"Total: {len(episodes)} episodes\n"
            f"Select an episode to download:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error in episodes callback: {e}")
        await callback.message.edit_text(f"❌ Error: {str(e)}")

@app.on_callback_query(filters.regex(r"^ep_"))
async def episode_download_callback(client: Client, callback: CallbackQuery):
    """Handle individual episode download"""
    episode_id = callback.data.split("_")[1]

    user_id = callback.from_user.id
    episodes = user_data.get(user_id, {}).get("episodes", [])

    # Find episode
    episode = None
    for ep in episodes:
        if ep.get("id") == episode_id:
            episode = ep
            break

    if not episode:
        await callback.answer("❌ Episode not found", show_alert=True)
        return

    await callback.answer("✅ Added to download queue")

    # Add to download queue
    await download_manager.add_to_queue(user_id, episode)

@app.on_callback_query(filters.regex(r"^download_all_"))
async def download_all_callback(client: Client, callback: CallbackQuery):
    """Handle download all episodes"""
    series_id = callback.data.split("_")[2]
    user_id = callback.from_user.id

    await callback.message.edit_text("⏳ Preparing to download all episodes...")

    try:
        episodes = await download_manager.api.get_episodes(series_id, include_unreleased=False)

        if not episodes:
            await callback.message.edit_text("❌ No episodes found.")
            return

        # Add all to queue
        for episode in episodes:
            await download_manager.add_to_queue(user_id, episode)

        await callback.message.edit_text(
            f"✅ **Added {len(episodes)} episodes to download queue!**\n\n"
            f"Downloads will start automatically. Please wait..."
        )

    except Exception as e:
        logger.error(f"Error in download all: {e}")
        await callback.message.edit_text(f"❌ Error: {str(e)}")

@app.on_callback_query(filters.regex(r"^unreleased_"))
async def unreleased_callback(client: Client, callback: CallbackQuery):
    """Handle unreleased episodes request"""
    series_id = callback.data.split("_")[1]

    await callback.message.edit_text("⏳ Fetching unreleased episodes...")

    try:
        episodes = await download_manager.api.get_episodes(series_id, include_unreleased=True)
        unreleased = [ep for ep in episodes if ep.get("is_released") == False]

        if not unreleased:
            await callback.message.edit_text("ℹ️ No unreleased episodes found.")
            return

        # Create keyboard with unreleased episodes
        keyboard = []
        for episode in unreleased[:10]:
            ep_title = episode.get("title", "Unknown")
            ep_id = episode.get("id")
            ep_num = episode.get("episode_number", "?")
            keyboard.append([
                InlineKeyboardButton(
                    f"🔒 Ep {ep_num}: {ep_title[:40]}",
                    callback_data=f"ep_{ep_id}"
                )
            ])

        keyboard.append([InlineKeyboardButton("« Back", callback_data=f"series_{series_id}")])

        await callback.message.edit_text(
            f"🔓 **Unreleased Episodes**\n\n"
            f"Found {len(unreleased)} unreleased episodes:\n"
            f"(These may not be available for download)",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error fetching unreleased episodes: {e}")
        await callback.message.edit_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("status") & filters.private)
@owner_only
async def status_command(client: Client, message: Message):
    """Status command for owners"""
    queue_size = download_manager.queue.qsize()
    active = len(download_manager.active_downloads)

    status_text = (
        "📊 **Bot Status**\n\n"
        f"Queue Size: {queue_size}\n"
        f"Active Downloads: {active}\n"
        f"Total Users: {len(user_data)}\n"
    )

    await message.reply_text(status_text)

# ==================== MAIN ====================
async def main():
    """Main function"""
    logger.info("Starting Pocket FM Downloader Bot...")

    # Start download queue processor
    asyncio.create_task(download_manager.process_queue(app))

    # Start bot
    await app.start()
    logger.info("Bot started successfully!")

    # Keep alive
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        app.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        asyncio.run(download_manager.api.close_session())
