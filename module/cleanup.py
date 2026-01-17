"""Cleanup module for removing already-downloaded messages and bot status messages."""

import asyncio
import os
import time
from datetime import datetime
from typing import Dict, List, Set, Union

import pyrogram
from loguru import logger

from module.app import Application, DownloadStatus
from module.language import _t


class CleanupManager:
    """Manages cleanup of already-downloaded messages and bot status messages."""

    def __init__(
        self,
        app: Application,
        client: pyrogram.Client,
        idle_timeout: int = 10800,  # 3 hours in seconds
        enabled: bool = True,
    ):
        """
        Initialize the CleanupManager.

        Parameters
        ----------
        app : Application
            The application instance
        client : pyrogram.Client
            The Pyrogram client instance
        idle_timeout : int, optional
            Time in seconds to wait after last download before cleanup (default: 3 hours)
        enabled : bool, optional
            Whether cleanup is enabled (default: True)
        """
        self.app = app
        self.client = client
        self.idle_timeout = idle_timeout
        self.enabled = enabled
        self.last_download_time = time.time()
        self.cleanup_running = False
        self.skipped_messages: Dict[Union[int, str], Set[int]] = {}
        self.bot_status_messages: Dict[Union[int, str], List[int]] = {}
        self.is_running = True

    def update_activity(self):
        """Update the last download activity timestamp."""
        self.last_download_time = time.time()

    def add_skipped_message(
        self, chat_id: Union[int, str], message_id: int, reason: str = None
    ):
        """
        Track a skipped message for potential cleanup.

        Parameters
        ----------
        chat_id : Union[int, str]
            The chat ID where the message is located
        message_id : int
            The message ID that was skipped
        reason : str, optional
            The reason for skipping (for logging)
        """
        if chat_id not in self.skipped_messages:
            self.skipped_messages[chat_id] = set()
        self.skipped_messages[chat_id].add(message_id)

    def add_bot_status_message(self, chat_id: Union[int, str], message_id: int):
        """
        Track a bot status message for cleanup.

        Parameters
        ----------
        chat_id : Union[int, str]
            The chat ID where the status message is located
        message_id : int
            The message ID of the status message
        """
        if chat_id not in self.bot_status_messages:
            self.bot_status_messages[chat_id] = []
        self.bot_status_messages[chat_id].append(message_id)

    async def check_and_cleanup(self):
        """
        Background task that checks for idle timeout and triggers cleanup.
        """
        logger.info(_t("Cleanup manager started"))

        while self.is_running:
            try:
                await asyncio.sleep(60)  # Check every minute

                if not self.enabled:
                    continue

                idle_time = time.time() - self.last_download_time

                if idle_time >= self.idle_timeout and not self.cleanup_running:
                    logger.info(
                        f"{_t('No downloads for')} {self.idle_timeout / 3600} {_t('hours')}, "
                        f"{_t('starting cleanup')}..."
                    )
                    await self.perform_cleanup()

            except Exception as e:
                logger.exception(f"{_t('Error in cleanup check')}: {e}")

    async def perform_cleanup(self):
        """
        Perform the cleanup of already-downloaded messages and bot status messages.
        """
        if self.cleanup_running:
            logger.warning(_t("Cleanup already running, skipping"))
            return

        self.cleanup_running = True
        cleanup_start_time = datetime.now()

        try:
            logger.info(_t("Starting cleanup process"))

            total_deleted = 0
            total_skipped_logged = 0

            # Clean up skipped messages (already downloaded)
            for chat_id, message_ids in self.skipped_messages.items():
                try:
                    deleted_count = await self._cleanup_chat_messages(
                        chat_id, list(message_ids)
                    )
                    total_deleted += deleted_count
                except Exception as e:
                    logger.error(
                        f"{_t('Error cleaning up chat')} {chat_id}: {e}",
                        exc_info=True,
                    )

            # Clean up bot status messages
            for chat_id, message_ids in self.bot_status_messages.items():
                try:
                    await self._cleanup_bot_messages(chat_id, message_ids)
                except Exception as e:
                    logger.error(
                        f"{_t('Error cleaning up bot messages in chat')} {chat_id}: {e}",
                        exc_info=True,
                    )

            # Log skipped items that weren't downloaded
            total_skipped_logged = await self._log_non_downloaded_skips()

            # Clear tracking dictionaries after successful cleanup
            self.skipped_messages.clear()
            self.bot_status_messages.clear()

            cleanup_duration = (datetime.now() - cleanup_start_time).total_seconds()

            logger.success(
                f"{_t('Cleanup completed')} - "
                f"{_t('Deleted')}: {total_deleted}, "
                f"{_t('Logged skipped items')}: {total_skipped_logged}, "
                f"{_t('Duration')}: {cleanup_duration:.2f}s"
            )

        except Exception as e:
            logger.exception(f"{_t('Error during cleanup')}: {e}")
        finally:
            self.cleanup_running = False
            # Reset the timer after cleanup
            self.last_download_time = time.time()

    async def _cleanup_chat_messages(
        self, chat_id: Union[int, str], message_ids: List[int]
    ) -> int:
        """
        Delete messages from a chat that were skipped because already downloaded.

        Parameters
        ----------
        chat_id : Union[int, str]
            The chat ID
        message_ids : List[int]
            List of message IDs to delete

        Returns
        -------
        int
            Number of messages deleted
        """
        if not message_ids:
            return 0

        deleted_count = 0

        try:
            # Delete in batches of 100 (Telegram API limit)
            batch_size = 100
            for i in range(0, len(message_ids), batch_size):
                batch = message_ids[i : i + batch_size]

                try:
                    # Only delete messages that were actually skipped because already downloaded
                    await self.client.delete_messages(
                        chat_id=chat_id, message_ids=batch
                    )
                    deleted_count += len(batch)
                    logger.info(
                        f"{_t('Deleted')} {len(batch)} {_t('already-downloaded messages from chat')} {chat_id}"
                    )

                    # Add a small delay to avoid rate limiting
                    await asyncio.sleep(1)

                except pyrogram.errors.exceptions.flood_420.FloodWait as wait_err:
                    logger.warning(
                        f"FloodWait {wait_err.value}s when deleting messages"
                    )
                    await asyncio.sleep(wait_err.value)
                except Exception as e:
                    logger.error(
                        f"{_t('Error deleting message batch')}: {e}", exc_info=True
                    )

        except Exception as e:
            logger.error(
                f"{_t('Error in cleanup for chat')} {chat_id}: {e}", exc_info=True
            )

        return deleted_count

    async def _cleanup_bot_messages(
        self, chat_id: Union[int, str], message_ids: List[int]
    ):
        """
        Delete bot status messages.

        Parameters
        ----------
        chat_id : Union[int, str]
            The chat ID
        message_ids : List[int]
            List of bot message IDs to delete
        """
        if not message_ids:
            return

        try:
            # Delete in batches
            batch_size = 100
            for i in range(0, len(message_ids), batch_size):
                batch = message_ids[i : i + batch_size]

                try:
                    await self.client.delete_messages(
                        chat_id=chat_id, message_ids=batch
                    )
                    logger.info(
                        f"{_t('Deleted')} {len(batch)} {_t('bot status messages from chat')} {chat_id}"
                    )
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(
                        f"{_t('Error deleting bot messages')}: {e}", exc_info=True
                    )

        except Exception as e:
            logger.error(
                f"{_t('Error cleaning up bot messages')}: {e}", exc_info=True
            )

    async def _log_non_downloaded_skips(self) -> int:
        """
        Log information about messages that were skipped for reasons other than being already downloaded.

        Returns
        -------
        int
            Number of items logged
        """
        logged_count = 0

        try:
            log_file = os.path.join(self.app.log_file_path, "skipped_items.log")

            # Check all chat download configs for skipped messages
            for chat_id, config in self.app.chat_download_config.items():
                if hasattr(config, "node") and config.node:
                    node = config.node

                    # Find messages that were skipped but not because they were already downloaded
                    for msg_id, status in node.download_status.items():
                        if status == DownloadStatus.SkipDownload:
                            # Check if this was NOT in our tracked skipped messages
                            # (meaning it was skipped for a different reason)
                            if (
                                chat_id not in self.skipped_messages
                                or msg_id not in self.skipped_messages[chat_id]
                            ):
                                # Log this message
                                with open(log_file, "a", encoding="utf-8") as f:
                                    timestamp = datetime.now().isoformat()
                                    f.write(
                                        f"[{timestamp}] Chat: {chat_id}, Message ID: {msg_id}, "
                                        f"Reason: Skipped (not already downloaded)\n"
                                    )
                                logged_count += 1

            if logged_count > 0:
                logger.info(
                    f"{_t('Logged')} {logged_count} {_t('skipped items to')} {log_file}"
                )

        except Exception as e:
            logger.error(f"{_t('Error logging skipped items')}: {e}", exc_info=True)

        return logged_count

    def stop(self):
        """Stop the cleanup manager."""
        self.is_running = False
        logger.info(_t("Cleanup manager stopped"))
