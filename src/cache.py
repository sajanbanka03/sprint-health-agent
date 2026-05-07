"""
Smart Cache Module for Sprint Health Agent

Implements two-tier caching:
1. Historical Sprint Cache - Persistent file-based cache for closed sprints (never changes)
2. Current Sprint Cache - In-memory with TTL for active sprint data

Author: Sajan Banka
Created: 2026
Copyright (c) 2026 Sajan Banka. All rights reserved.
"""
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"


@dataclass
class CacheEntry:
    """Represents a cached item with metadata"""
    data: Any
    created_at: str
    expires_at: Optional[str]
    cache_type: str  # 'historical' or 'current'
    sprint_id: Optional[int] = None
    board_id: Optional[int] = None


class SprintCache:
    """
    Smart cache for sprint data.

    - Historical sprints: Cached permanently (file-based)
    - Current sprint: Cached with TTL (in-memory)
    """

    def __init__(self, current_ttl_minutes: int = 10):
        """
        Initialize the cache.

        Args:
            current_ttl_minutes: TTL for current sprint cache (default 10 min)
        """
        self.current_ttl = timedelta(minutes=current_ttl_minutes)
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

        # Ensure cache directory exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        logger.info(f"SprintCache initialized with TTL={current_ttl_minutes}min")

    def _get_cache_key(self, prefix: str, board_id: int, sprint_id: Optional[int] = None) -> str:
        """Generate a cache key"""
        if sprint_id:
            return f"{prefix}_{board_id}_{sprint_id}"
        return f"{prefix}_{board_id}"

    def _get_file_path(self, cache_key: str) -> Path:
        """Get file path for persistent cache"""
        return CACHE_DIR / f"{cache_key}.json"

    # ============================================
    # Historical Sprint Cache (Persistent)
    # ============================================

    def get_historical_velocity(self, board_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached historical velocity data.

        Returns None if not cached or if cache is invalid.
        """
        cache_key = self._get_cache_key("velocity", board_id)
        file_path = self._get_file_path(cache_key)

        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    entry = json.load(f)
                logger.info(f"Historical velocity cache HIT for board {board_id}")
                return entry.get('data')
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read velocity cache: {e}")
                return None

        logger.info(f"Historical velocity cache MISS for board {board_id}")
        return None

    def set_historical_velocity(self, board_id: int, velocity_data: list, current_sprint_id: int) -> None:
        """
        Cache historical velocity data.

        Args:
            board_id: The board ID
            velocity_data: List of velocity data from closed sprints
            current_sprint_id: Current active sprint ID (for invalidation tracking)
        """
        cache_key = self._get_cache_key("velocity", board_id)
        file_path = self._get_file_path(cache_key)

        entry = {
            'data': velocity_data,
            'created_at': datetime.now().isoformat(),
            'expires_at': None,  # Never expires
            'cache_type': 'historical',
            'board_id': board_id,
            'current_sprint_id': current_sprint_id  # Track which sprint was active
        }

        try:
            with open(file_path, 'w') as f:
                json.dump(entry, f, default=str)
            logger.info(f"Cached historical velocity for board {board_id}")
        except IOError as e:
            logger.error(f"Failed to write velocity cache: {e}")

    def should_refresh_historical(self, board_id: int, current_sprint_id: int) -> bool:
        """
        Check if historical cache needs refresh (sprint changed).

        Returns True if:
        - No cache exists
        - Current sprint ID differs from cached sprint ID
        """
        cache_key = self._get_cache_key("velocity", board_id)
        file_path = self._get_file_path(cache_key)

        if not file_path.exists():
            return True

        try:
            with open(file_path, 'r') as f:
                entry = json.load(f)
            cached_sprint_id = entry.get('current_sprint_id')

            if cached_sprint_id != current_sprint_id:
                logger.info(f"Sprint changed ({cached_sprint_id} -> {current_sprint_id}), refreshing historical cache")
                return True

            return False
        except (json.JSONDecodeError, IOError):
            return True

    # ============================================
    # Current Sprint Cache (In-Memory with TTL)
    # ============================================

    def get_current_sprint(self, board_id: int, team_name: str) -> Optional[Any]:
        """
        Get cached current sprint report.

        Returns None if not cached or expired.
        """
        cache_key = f"current_{board_id}_{team_name}"

        with self._lock:
            if cache_key not in self._memory_cache:
                logger.info(f"Current sprint cache MISS for {team_name}")
                return None

            entry = self._memory_cache[cache_key]
            expires_at = datetime.fromisoformat(entry.expires_at)

            if datetime.now() > expires_at:
                logger.info(f"Current sprint cache EXPIRED for {team_name}")
                del self._memory_cache[cache_key]
                return None

            logger.info(f"Current sprint cache HIT for {team_name}")
            return entry.data

    def set_current_sprint(self, board_id: int, team_name: str, report_data: Any) -> None:
        """
        Cache current sprint report.

        Args:
            board_id: The board ID
            team_name: Team name
            report_data: The report object to cache
        """
        cache_key = f"current_{board_id}_{team_name}"
        expires_at = datetime.now() + self.current_ttl

        entry = CacheEntry(
            data=report_data,
            created_at=datetime.now().isoformat(),
            expires_at=expires_at.isoformat(),
            cache_type='current',
            board_id=board_id
        )

        with self._lock:
            self._memory_cache[cache_key] = entry
            logger.info(f"Cached current sprint for {team_name}, expires at {expires_at}")

    def invalidate_current_sprint(self, board_id: int = None, team_name: str = None) -> None:
        """
        Invalidate current sprint cache.

        Args:
            board_id: If provided, invalidate for specific board
            team_name: If provided, invalidate for specific team
            If neither provided, invalidate all current sprint caches
        """
        with self._lock:
            if board_id and team_name:
                cache_key = f"current_{board_id}_{team_name}"
                if cache_key in self._memory_cache:
                    del self._memory_cache[cache_key]
                    logger.info(f"Invalidated cache for {team_name}")
            else:
                # Invalidate all current sprint caches
                keys_to_delete = [k for k in self._memory_cache.keys() if k.startswith("current_")]
                for key in keys_to_delete:
                    del self._memory_cache[key]
                logger.info(f"Invalidated {len(keys_to_delete)} current sprint caches")

    # ============================================
    # Cache Info & Management
    # ============================================

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about current cache state"""
        # Count historical cache files
        historical_count = len(list(CACHE_DIR.glob("velocity_*.json")))

        # Count current sprint caches
        with self._lock:
            current_count = len(self._memory_cache)
            current_items = []
            for key, entry in self._memory_cache.items():
                expires_at = datetime.fromisoformat(entry.expires_at)
                remaining = (expires_at - datetime.now()).total_seconds()
                current_items.append({
                    'key': key,
                    'expires_in_seconds': max(0, int(remaining)),
                    'created_at': entry.created_at
                })

        return {
            'historical_cache_count': historical_count,
            'current_cache_count': current_count,
            'current_cache_items': current_items,
            'cache_directory': str(CACHE_DIR),
            'current_ttl_minutes': self.current_ttl.total_seconds() / 60
        }

    def clear_all_cache(self) -> Dict[str, int]:
        """Clear all caches (both historical and current)"""
        # Clear historical cache files
        historical_cleared = 0
        for file_path in CACHE_DIR.glob("*.json"):
            try:
                file_path.unlink()
                historical_cleared += 1
            except IOError:
                pass

        # Clear current sprint cache
        with self._lock:
            current_cleared = len(self._memory_cache)
            self._memory_cache.clear()

        logger.info(f"Cleared {historical_cleared} historical + {current_cleared} current cache entries")

        return {
            'historical_cleared': historical_cleared,
            'current_cleared': current_cleared
        }


# Global cache instance
_cache_instance: Optional[SprintCache] = None


def get_cache(ttl_minutes: int = 10) -> SprintCache:
    """Get or create the global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SprintCache(current_ttl_minutes=ttl_minutes)
    return _cache_instance

