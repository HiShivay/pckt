"""
Pocket FM Downloader Bot - Main Entry Point
Professional production-ready bot with proper architecture
"""

import sys
import asyncio
import logging
from pathlib import Path

from pyrogram import Client
from config import config
from api_handler import api_handler
from download_manager import download_manager
from handlers import register_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Validate configuration
def validate_config():
    """Validate that all required configuration is set"""

    logger.info("Validating configuration...")

    errors = []

    if not config.API_ID or config.API_ID == 0:
        errors.append("❌ API_ID not set in .env")

    if not config.API_HASH:
        errors.append("❌ API_HASH not set in .env")

    if not config.BOT_TOKEN:
        errors.append("❌ BOT_TOKEN not set in .env")

    if not config.OWNER_IDS or config.OWNER_IDS == [0]:
        errors.append("⚠️ OWNER_IDS not set in .env")

    if errors:
        for error in errors:
            logger.error(error)
        return False

    logger.info("✅ Configuration validated successfully")
    return True

# Create bot instance
def create_bot():
    """Create and configure Pyrogram client"""

    logger.info("Creating Pyrogram client...")

    app = Client(
        "pocketfm_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workers=4
    )

    logger.info("✅ Pyrogram client created")
    return app

# Main async function
async def main():
    """Main bot execution"""

    logger.info("=" * 60)
    logger.info("🎧 Pocket FM Downloader Bot - Starting")
    logger.info("=" * 60)

    # Validate
    if not validate_config():
        logger.error("Configuration validation failed!")
        return

    # Create bot
    app = create_bot()

    # Register handlers
    register_handlers(app)

    # Initialize API
    await api_handler.init_session()

    # Create download directory
    Path(config.DOWNLOAD_PATH).mkdir(parents=True, exist_ok=True)
    logger.info(f"Download directory: {config.DOWNLOAD_PATH}")

    # Start queue processor
    queue_processor_task = asyncio.create_task(
        download_manager.process_queue(app)
    )

    logger.info("📥 Download queue processor started")

    # Start bot
    async with app:
        logger.info("🤖 Bot connected to Telegram!")
        logger.info("=" * 60)
        logger.info("✅ Bot is running. Press Ctrl+C to stop")
        logger.info("=" * 60)

        try:
            # Keep bot running
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("\n🛑 Shutting down...")

# Entry point
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info("Cleaning up...")
        asyncio.run(api_handler.close_session())
        logger.info("Goodbye! 👋")
