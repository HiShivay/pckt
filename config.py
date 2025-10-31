"""
Configuration file for Pocket FM Downloader Bot
All settings in one place for easy management
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""

    # ==================== TELEGRAM ====================
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    OWNER_IDS = list(map(int, os.getenv("OWNER_IDS", "0").split(",")))

    # ==================== FILE PATHS ====================
    DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", "downloads")
    LOG_PATH = "pocketfm_bot.log"

    # ==================== DOWNLOAD SETTINGS ====================
    MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
    CHUNK_SIZE = 1024 * 1024  # 1MB
    REQUEST_TIMEOUT = 15
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2  # seconds

    # ==================== POCKET FM API ====================
    # Note: These are the actual working endpoints that need to be discovered
    # Follow the reverse engineering guide to find real endpoints

    # Possible base URLs (try these)
    POCKETFM_BASE_URLS = [
        "https://api.pocketfm.in",
        "https://api.pocketfm.com",
        "https://api-cdn.pocketfm.com",
        "https://gateway.pocketfm.com",
    ]

    # API Version
    API_VERSION = "v1"

    # Default Headers - Mimic official app
    DEFAULT_HEADERS = {
        "User-Agent": "okhttp/4.9.3",  # Official app uses okhttp
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Client-Version": "8.12.3",
        "X-Platform": "android",
        "X-Device-Type": "Mobile",
    }

    # ==================== PAGINATION ====================
    RESULTS_PER_PAGE = 10
    EPISODES_PER_PAGE = 15

    # ==================== FEATURES ====================
    ENABLE_MOCK_MODE = True  # Use mock data when API fails
    ENABLE_LOGGING = True
    DEBUG_MODE = False

    # ==================== DATABASE ====================
    # For future: to store user preferences, download history, etc.
    # DB_URL = "sqlite:///pocketfm_bot.db"

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG_MODE = True
    ENABLE_MOCK_MODE = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG_MODE = False
    ENABLE_MOCK_MODE = False

# Select config based on environment
def get_config():
    """Get appropriate config based on environment"""
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        return ProductionConfig()
    return DevelopmentConfig()

# Make config accessible
config = get_config()
