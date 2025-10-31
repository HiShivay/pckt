"""
API Handler for Pocket FM
Manages all API calls with proper error handling and retry logic
"""

import asyncio
import logging
import aiohttp
from typing import Optional, List, Dict, Any
from config import config

logger = logging.getLogger(__name__)

class PocketFMAPIHandler:
    """Handles all Pocket FM API operations"""

    def __init__(self):
        self.base_urls = config.POCKETFM_BASE_URLS
        self.current_url_index = 0
        self.session: Optional[aiohttp.ClientSession] = None
        self.retry_attempts = config.RETRY_ATTEMPTS
        self.retry_delay = config.RETRY_DELAY

    async def init_session(self):
        """Initialize aiohttp session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
            self.session = aiohttp.ClientSession(
                headers=config.DEFAULT_HEADERS,
                timeout=timeout
            )
            logger.info("API session initialized")

    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            logger.info("API session closed")

    def _get_base_url(self) -> str:
        """Get current base URL"""
        if self.current_url_index >= len(self.base_urls):
            self.current_url_index = 0
        return self.base_urls[self.current_url_index]

    async def _rotate_url(self):
        """Rotate to next base URL"""
        self.current_url_index = (self.current_url_index + 1) % len(self.base_urls)
        logger.warning(f"Rotated to URL: {self._get_base_url()}")

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """
        Make HTTP request with retry logic

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional request parameters

        Returns:
            Response JSON or None
        """
        await self.init_session()

        for attempt in range(self.retry_attempts):
            try:
                base_url = self._get_base_url()
                url = f"{base_url}{endpoint}"

                logger.debug(f"Request [{attempt+1}/{self.retry_attempts}]: {method} {url}")

                async with self.session.request(method, url, ssl=False, **kwargs) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        logger.warning(f"404 on {endpoint}")
                        await self._rotate_url()
                    elif response.status in [429, 503]:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))

            except asyncio.TimeoutError:
                logger.warning(f"Timeout on attempt {attempt + 1}")
                await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Request error: {e}")
                await self._rotate_url()

        return None

    async def search_series(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for series

        IMPORTANT: These endpoints are placeholders.
        You MUST reverse engineer the actual endpoints and update them.
        """

        # Try different endpoint variations
        endpoints = [
            ("/api/v1/search", {"q": query, "type": "series", "limit": limit}),
            ("/api/v2/search", {"q": query, "type": "series", "limit": limit}),
            ("/search", {"q": query, "type": "series", "limit": limit}),
            ("/series/search", {"q": query, "limit": limit}),
        ]

        for endpoint, params in endpoints:
            try:
                response = await self._make_request("GET", endpoint, params=params)
                if response:
                    # Try different response structures
                    results = (
                        response.get("results", []) or
                        response.get("data", {}).get("series", []) or
                        response.get("data", []) or
                        response.get("series", [])
                    )

                    if results:
                        logger.info(f"Search successful: found {len(results)} results")
                        return results

            except Exception as e:
                logger.error(f"Search endpoint {endpoint} failed: {e}")

        logger.warning("All search endpoints failed")
        return []

    async def get_series_details(self, series_id: str) -> Optional[Dict[str, Any]]:
        """Get series details"""

        endpoints = [
            f"/api/v1/series/{series_id}",
            f"/api/v2/series/{series_id}",
            f"/series/{series_id}",
        ]

        for endpoint in endpoints:
            try:
                response = await self._make_request("GET", endpoint)
                if response:
                    logger.info(f"Series details retrieved: {endpoint}")
                    return response
            except Exception as e:
                logger.error(f"Failed to get series details: {e}")

        return None

    async def get_episodes(self, series_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get episodes for a series"""

        endpoints = [
            f"/api/v1/series/{series_id}/episodes",
            f"/api/v2/series/{series_id}/episodes",
            f"/series/{series_id}/episodes",
        ]

        for endpoint in endpoints:
            try:
                response = await self._make_request(
                    "GET",
                    endpoint,
                    params={"limit": limit}
                )

                if response:
                    episodes = (
                        response.get("episodes", []) or
                        response.get("data", []) or
                        response.get("items", [])
                    )

                    if episodes:
                        logger.info(f"Episodes retrieved: {len(episodes)} episodes")
                        return episodes

            except Exception as e:
                logger.error(f"Failed to get episodes: {e}")

        return []

    async def get_stream_url(self, episode_id: str, quality: str = "high") -> Optional[str]:
        """
        Get episode stream URL
        CRITICAL ENDPOINT - Must be discovered via reverse engineering
        """

        endpoints = [
            f"/api/v1/episodes/{episode_id}/stream",
            f"/api/v2/episodes/{episode_id}/stream",
            f"/episodes/{episode_id}/stream",
            f"/stream/{episode_id}",
        ]

        for endpoint in endpoints:
            try:
                response = await self._make_request(
                    "GET",
                    endpoint,
                    params={"quality": quality}
                )

                if response:
                    url = response.get("url") or response.get("stream_url")
                    if url:
                        logger.info(f"Stream URL obtained")
                        return url

            except Exception as e:
                logger.error(f"Failed to get stream URL: {e}")

        logger.warning("Could not get stream URL")
        return None

    async def download_file(
        self,
        url: str,
        filepath: str,
        progress_callback=None
    ) -> bool:
        """Download file with progress tracking"""

        await self.init_session()

        try:
            logger.info(f"Starting download: {filepath}")

            async with self.session.get(url, ssl=False) as response:
                if response.status in [200, 206]:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    import aiofiles
                    async with aiofiles.open(filepath, 'wb') as f:
                        async for chunk in response.content.iter_chunked(config.CHUNK_SIZE):
                            await f.write(chunk)
                            downloaded += len(chunk)

                            if progress_callback and total_size > 0:
                                progress = (downloaded / total_size) * 100
                                await progress_callback(progress, downloaded, total_size)

                    logger.info(f"Download complete: {filepath}")
                    return True
                else:
                    logger.error(f"Download failed: HTTP {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Download error: {e}")
            return False

# Global instance
api_handler = PocketFMAPIHandler()
