"""
Bot Command Handlers
All Telegram bot handlers in one place
"""

import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import config
from api_handler import api_handler
from download_manager import download_manager

logger = logging.getLogger(__name__)

# Store user data
user_data = {}

# ==================== COMMAND HANDLERS ====================

async def cmd_start(client: Client, message: Message):
    """Start command"""
    await message.reply_text(
        "🎧 **Welcome to Pocket FM Downloader!**\n\n"
        "Download your favorite audio series from Pocket FM.\n\n"
        "**Available Commands:**\n"
        "• /search <query> - Search for a series\n"
        "• /help - Show help\n"
        "• /about - About this bot\n\n"
        "**Example:** /search saving nora"
    )

async def cmd_help(client: Client, message: Message):
    """Help command"""
    await message.reply_text(
        "📚 **Help & Guide**\n\n"
        "**How to use:**\n"
        "1. Send /search <series name>\n"
        "2. Select a series from results\n"
        "3. Choose episodes to download\n"
        "4. Bot will download and upload to Telegram\n\n"
        "**Supported:**\n"
        "✅ Free & Premium content\n"
        "✅ Individual episode downloads\n"
        "✅ Bulk series downloads\n"
        "✅ Unreleased episodes (if available)\n\n"
        "**Note:** Large files may take time to download.\n"
        "Please be patient!"
    )

async def cmd_about(client: Client, message: Message):
    """About command"""
    await message.reply_text(
        "ℹ️ **About This Bot**\n\n"
        "**Pocket FM Downloader Bot**\n"
        "Version: 2.0.0\n"
        "Framework: Pyrogram\n\n"
        "This bot helps you download and manage\n"
        "Pocket FM audio series.\n\n"
        "**Features:**\n"
        "🔍 Advanced search\n"
        "📋 Episode selection\n"
        "⬇️ Queue management\n"
        "📊 Progress tracking\n"
        "🔓 Unreleased content\n\n"
        "**Disclaimer:**\n"
        "Respect copyright and Terms of Service\n"
        "Use for personal enjoyment only"
    )

async def cmd_search(client: Client, message: Message):
    """Search for series"""

    try:
        # Extract query
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text(
                "❓ **Usage:** /search <series name>\n\n"
                "**Examples:**\n"
                "• /search saving nora\n"
                "• /search k for king\n"
                "• /search love"
            )
            return

        query = parts[1]
        status = await message.reply_text(f"🔍 Searching for: **{query}**...")

        # Search
        results = await api_handler.search_series(query)

        if not results:
            await status.edit_text(
                f"❌ No results found for: **{query}**\n\n"
                "Try a different search query"
            )
            return

        # Store results
        user_data[message.from_user.id] = {"search_results": results}

        # Create keyboard
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"📚 {r.get('title', 'Unknown')[:35]}",
                callback_data=f"series_{r['id']}"
            )] for r in results[:10]
        ])

        await status.edit_text(
            f"🔍 **Search Results:** {query}\n\n"
            f"Found {len(results)} series\n\n"
            "Select one to view episodes:",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        await message.reply_text(f"❌ Error: {str(e)[:200]}")

# ==================== CALLBACK HANDLERS ====================

async def callback_series(client: Client, callback: CallbackQuery):
    """Handle series selection"""

    try:
        series_id = callback.data.split("_", 1)[1]

        await callback.message.edit_text("⏳ Loading series details...")

        # Get details
        details = await api_handler.get_series_details(series_id)

        if not details:
            await callback.message.edit_text("❌ Failed to load series")
            return

        # Store
        if callback.from_user.id not in user_data:
            user_data[callback.from_user.id] = {}
        user_data[callback.from_user.id]["current_series"] = details
        user_data[callback.from_user.id]["series_id"] = series_id

        title = details.get("title", "Unknown")
        desc = details.get("description", "No description")
        episodes = details.get("total_episodes", "?")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 View Episodes", callback_data=f"episodes_{series_id}")],
            [InlineKeyboardButton("⬇️ Download All", callback_data=f"download_all_{series_id}")],
            [InlineKeyboardButton("« Back", callback_data="back_search")]
        ])

        await callback.message.edit_text(
            f"📚 **{title}**\n\n"
            f"Episodes: {episodes}\n\n"
            f"**About:** {desc[:200]}...",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Series callback error: {e}")
        await callback.answer(f"Error: {str(e)[:50]}", show_alert=True)

async def callback_episodes(client: Client, callback: CallbackQuery):
    """Show episodes"""

    try:
        series_id = callback.data.split("_", 1)[1]

        await callback.message.edit_text("⏳ Loading episodes...")

        # Get episodes
        episodes = await api_handler.get_episodes(series_id)

        if not episodes:
            await callback.message.edit_text("❌ No episodes found")
            return

        # Store
        user_data[callback.from_user.id]["episodes"] = episodes

        # Create keyboard (first 10)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"Ep {ep.get('episode_number', '?')}: {ep.get('title', 'Unknown')[:30]}",
                callback_data=f"ep_{ep['id']}"
            )] for ep in episodes[:10]
        ])

        # Add back button
        keyboard.inline_keyboard.append([
            InlineKeyboardButton("« Back", callback_data=f"series_{series_id}")
        ])

        await callback.message.edit_text(
            f"📋 **Episodes** ({len(episodes)} total)\n\n"
            "Select an episode to download:",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Episodes error: {e}")
        await callback.answer(f"Error: {str(e)[:50]}", show_alert=True)

async def callback_episode_download(client: Client, callback: CallbackQuery):
    """Download single episode"""

    try:
        episode_id = callback.data.split("_", 1)[1]
        user_id = callback.from_user.id

        # Find episode
        episodes = user_data.get(user_id, {}).get("episodes", [])
        episode = None

        for ep in episodes:
            if ep.get("id") == episode_id:
                episode = ep
                break

        if not episode:
            await callback.answer("❌ Episode not found", show_alert=True)
            return

        # Add to queue
        await download_manager.add_to_queue(user_id, episode)

        await callback.answer(
            "✅ Added to download queue!\n"
            "Download will start shortly...",
            show_alert=False
        )

    except Exception as e:
        logger.error(f"Episode callback error: {e}")
        await callback.answer(f"Error: {str(e)[:50]}", show_alert=True)

async def callback_download_all(client: Client, callback: CallbackQuery):
    """Download all episodes"""

    try:
        series_id = callback.data.split("_", 2)[2]
        user_id = callback.from_user.id

        await callback.message.edit_text(
            "⏳ Loading all episodes...\n"
            "This may take a moment..."
        )

        # Get all episodes
        episodes = await api_handler.get_episodes(series_id, limit=500)

        if not episodes:
            await callback.message.edit_text("❌ No episodes found")
            return

        # Limit to first 50
        episodes = episodes[:50]

        # Add all to queue
        for ep in episodes:
            await download_manager.add_to_queue(user_id, ep)

        await callback.message.edit_text(
            f"✅ **Queued {len(episodes)} episodes!**\n\n"
            f"Downloads will process automatically.\n"
            f"This may take several hours depending on your internet."
        )

    except Exception as e:
        logger.error(f"Download all error: {e}")
        await callback.answer(f"Error: {str(e)[:50]}", show_alert=True)

# ==================== REGISTER HANDLERS ====================

def register_handlers(app: Client):
    """Register all bot handlers"""

    # Command handlers
    app.on_message(filters.command("start") & filters.private)(cmd_start)
    app.on_message(filters.command("help") & filters.private)(cmd_help)
    app.on_message(filters.command("about") & filters.private)(cmd_about)
    app.on_message(filters.command("search") & filters.private)(cmd_search)

    # Callback handlers
    app.on_callback_query(filters.regex(r"^series_"))(callback_series)
    app.on_callback_query(filters.regex(r"^episodes_"))(callback_episodes)
    app.on_callback_query(filters.regex(r"^ep_"))(callback_episode_download)
    app.on_callback_query(filters.regex(r"^download_all_"))(callback_download_all)

    logger.info("All handlers registered")
