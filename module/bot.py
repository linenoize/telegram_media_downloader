"""Bot for media downloader"""

import asyncio
import os
from datetime import datetime
from typing import Callable, List, Optional, Tuple, Union

import pyrogram
from loguru import logger
from pyrogram import types
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from ruamel import yaml

import utils
from module.app import (
    Application,
    ChatDownloadConfig,
    ForwardStatus,
    QueryHandler,
    QueryHandlerStr,
    TaskNode,
    TaskType,
    UploadStatus,
)
from module.filter import Filter
from module.get_chat_history_v2 import get_chat_history_v2
from module.language import Language, _t
from module.pyrogram_extension import (
    check_user_permission,
    parse_link,
    proc_cache_forward,
    report_bot_forward_status,
    report_bot_status,
    retry,
    set_meta_data,
    upload_telegram_chat_message,
)
from module.search import add_search_handler
from utils.format import replace_date_time, validate_title
from utils.meta_data import MetaData

# pylint: disable = C0301, R0902

SUPPORTED_MEDIA_TYPES = [
    "audio",
    "document",
    "photo",
    "video",
    "voice",
    "animation",
    "video_note",
]

CATEGORY_ALIASES = {
    "image": ["photo"],
    "images": ["photo"],
    "photo": ["photo"],
    "photos": ["photo"],
    "document": ["document"],
    "documents": ["document"],
    "doc": ["document"],
    "docs": ["document"],
    "video": ["video"],
    "videos": ["video"],
    "audio": ["audio"],
    "audios": ["audio"],
    "voice": ["voice"],
    "voices": ["voice"],
    "animation": ["animation"],
    "animations": ["animation"],
    "gif": ["animation"],
    "gifs": ["animation"],
    "video_note": ["video_note"],
    "videonote": ["video_note"],
}


def _is_filter_token(token: str) -> bool:
    return any(op in token for op in ["<=", ">=", "==", "!=", ">", "<", "&", "|"])


def _normalize_extension(ext: str) -> Optional[str]:
    if not ext:
        return None
    ext = ext.strip().lower()
    if ext.startswith("."):
        ext = ext[1:]
    return ext or None


def _get_all_media_types(app: Application) -> List[str]:
    media_types = list(app.media_types) if app and app.media_types else []
    for media_type in SUPPORTED_MEDIA_TYPES:
        if media_type not in media_types:
            media_types.append(media_type)
    return media_types


def _reply_parameters(message: pyrogram.types.Message) -> types.ReplyParameters:
    return types.ReplyParameters(message_id=message.id)


def _track_bot_status_message(
    app: Optional[Application], chat_id: Union[int, str], message_id: int
):
    if not app or not app.cleanup_delete_bot_status:
        return
    cleanup_manager = getattr(app, "cleanup_manager", None)
    if cleanup_manager:
        cleanup_manager.add_bot_status_message(chat_id, message_id)


def _parse_selector_flags(
    tokens: List[str],
) -> Tuple[Optional[str], Optional[str], Optional[str], List[str]]:
    selector = None
    selector_mode = None
    error = None
    remaining: List[str] = []
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token.startswith("--type="):
            selector = token.split("=", 1)[1]
            selector_mode = "type"
        elif token.startswith("--ext="):
            selector = token.split("=", 1)[1]
            selector_mode = "ext"
        elif token in ["--type", "--ext"]:
            if idx + 1 >= len(tokens):
                error = f"{token} requires a value"
                break
            selector = tokens[idx + 1]
            selector_mode = "type" if token == "--type" else "ext"
            idx += 1
        else:
            remaining.append(token)
        idx += 1
    return selector, selector_mode, error, remaining


def _parse_text_dl_flags(tokens: List[str]) -> Tuple[str, Optional[str], List[str]]:
    mode = "text"
    mode_flag = None
    remaining: List[str] = []
    for token in tokens:
        if token in ["--urls", "--url"]:
            if mode_flag and mode_flag != "urls":
                return mode, "Please provide only one output mode flag.", tokens
            mode = "urls"
            mode_flag = "urls"
        elif token == "--both":
            if mode_flag and mode_flag != "both":
                return mode, "Please provide only one output mode flag.", tokens
            mode = "both"
            mode_flag = "both"
        elif token == "--text":
            if mode_flag and mode_flag != "text":
                return mode, "Please provide only one output mode flag.", tokens
            mode = "text"
            mode_flag = "text"
        else:
            remaining.append(token)
    return mode, None, remaining


def _parse_order_flags(tokens: List[str]) -> Tuple[bool, Optional[str], List[str]]:
    newest_first = False
    error = None
    remaining: List[str] = []
    for token in tokens:
        if token == "--newest":
            newest_first = True
        elif token.startswith("--order="):
            value = token.split("=", 1)[1].strip().lower()
            if value in ["newest", "desc", "latest"]:
                newest_first = True
            elif value in ["oldest", "asc", "earliest"]:
                newest_first = False
            else:
                error = f"Unsupported order value: {value}"
        else:
            remaining.append(token)
    return newest_first, error, remaining


def _resolve_selector(
    app: Application, selector: Optional[str], selector_mode: Optional[str]
) -> Tuple[Optional[List[str]], Optional[dict], Optional[str], Optional[str]]:
    if not selector:
        return None, None, None, None

    selector = selector.strip()
    selector_lower = selector.lower()

    if selector_mode == "type":
        category = CATEGORY_ALIASES.get(selector_lower)
        if category:
            return category, None, None, None
        if selector_lower in SUPPORTED_MEDIA_TYPES:
            return [selector_lower], None, None, None
        return None, None, None, f"Unknown category: {selector}"

    if selector_mode == "ext":
        ext = _normalize_extension(selector)
        if not ext:
            return None, None, None, f"Invalid extension: {selector}"
        media_types = _get_all_media_types(app)
        file_formats_override = {
            "audio": ["all"],
            "document": ["all"],
            "video": ["all"],
        }
        ext_filter = f"file_extension == '{ext}'"
        return media_types, file_formats_override, ext_filter, None

    if selector_lower in CATEGORY_ALIASES or selector_lower in SUPPORTED_MEDIA_TYPES:
        category = CATEGORY_ALIASES.get(selector_lower, [selector_lower])
        return category, None, None, None

    ext = _normalize_extension(selector)
    if not ext:
        return None, None, None, f"Invalid selector: {selector}"
    media_types = _get_all_media_types(app)
    file_formats_override = {
        "audio": ["all"],
        "document": ["all"],
        "video": ["all"],
    }
    ext_filter = f"file_extension == '{ext}'"
    return media_types, file_formats_override, ext_filter, None


class DownloadBot:
    """Download bot"""

    def __init__(self):
        self.bot = None
        self.client = None
        self.add_download_task: Callable = None
        self.download_chat_task: Callable = None
        self.app = None
        self.listen_forward_chat: dict = {}
        self.config: dict = {}
        self._yaml = yaml.YAML()
        self.config_path = os.path.join(os.path.abspath("."), "bot.yaml")
        self.download_command: dict = {}
        self.filter = Filter()
        self.bot_info = None
        self.task_node: dict = {}
        self.is_running = True
        self.allowed_user_ids: List[Union[int, str]] = []

        meta = MetaData(datetime(2022, 8, 5, 14, 35, 12), 0, "", 0, 0, 0, "", 0)
        self.filter.set_meta_data(meta)

        self.download_filter: List[str] = []
        self.task_id: int = 0
        self.reply_task = None

    def gen_task_id(self) -> int:
        """Gen task id"""
        self.task_id += 1
        return self.task_id

    def add_task_node(self, node: TaskNode):
        """Add task node"""
        self.task_node[node.task_id] = node

    def remove_task_node(self, task_id: int):
        """Remove task node"""
        self.task_node.pop(task_id)

    def stop_task(self, task_id: str):
        """Stop task"""
        if task_id == "all":
            for value in self.task_node.values():
                value.stop_transmission()
        else:
            try:
                task = self.task_node.get(int(task_id))
                if task:
                    task.stop_transmission()
            except Exception:
                return

    async def update_reply_message(self):
        """Update reply message"""
        while self.is_running:
            for key, value in self.task_node.copy().items():
                if value.is_running:
                    await report_bot_status(self.bot, value)

            for key, value in self.task_node.copy().items():
                if value.is_running and value.is_finish():
                    self.remove_task_node(key)
            await asyncio.sleep(3)

    def assign_config(self, _config: dict):
        """assign config from str.

        Parameters
        ----------
        _config: dict
            application config dict

        Returns
        -------
        bool
        """

        self.download_filter = _config.get("download_filter", self.download_filter)

        return True

    def update_config(self):
        """Update config from str."""
        self.config["download_filter"] = self.download_filter

        with open("d", "w", encoding="utf-8") as yaml_file:
            self._yaml.dump(self.config, yaml_file)

    async def start(
        self,
        app: Application,
        client: pyrogram.Client,
        add_download_task: Callable,
        download_chat_task: Callable,
    ):
        """Start bot"""
        self.bot = pyrogram.Client(
            app.application_name + "_bot",
            api_hash=app.api_hash,
            api_id=app.api_id,
            bot_token=app.bot_token,
            workdir=app.session_file_path,
            proxy=app.proxy,
        )

        # 命令列表
        commands = [
            types.BotCommand("help", _t("Help")),
            types.BotCommand(
                "get_info", _t("Get group and user info from message link")
            ),
            types.BotCommand(
                "get_url", _t("Get Telegram URL for a channel/group by username or ID")
            ),
            types.BotCommand(
                "download",
                _t(
                    "To download the video, use the method to directly enter /download to view"
                ),
            ),
            types.BotCommand(
                "text_dl",
                _t("Download message text or urls with filters: /text_dl <link> ..."),
            ),
            types.BotCommand(
                "dl",
                _t("Simplified download with date filtering: /dl <link> [start_date] [end_date]")
            ),
            types.BotCommand(
                "forward",
                _t("Forward video, use the method to directly enter /forward to view"),
            ),
            types.BotCommand(
                "listen_forward",
                _t(
                    "Listen forward, use the method to directly enter /listen_forward to view"
                ),
            ),
            types.BotCommand(
                "add_filter",
                _t(
                    "Add download filter, use the method to directly enter /add_filter to view"
                ),
            ),
            types.BotCommand("set_language", _t("Set language")),
            types.BotCommand("stop", _t("Stop bot download or forward")),
            types.BotCommand("search_mega", _t("Search for mega links in a chat")),
        ]

        self.app = app
        self.client = client
        self.add_download_task = add_download_task
        self.download_chat_task = download_chat_task

        # load config
        if os.path.exists(self.config_path):
            with open(self.config_path, encoding="utf-8") as f:
                config = self._yaml.load(f.read())
                if config:
                    self.config = config
                    self.assign_config(self.config)

        await self.bot.start()

        self.bot_info = await self.bot.get_me()

        for allowed_user_id in self.app.allowed_user_ids:
            try:
                chat = await self.client.get_chat(allowed_user_id)
                self.allowed_user_ids.append(chat.id)
            except Exception as e:
                logger.warning(f"set allowed_user_ids error: {e}")

        admin = await self.client.get_me()
        self.allowed_user_ids.append(admin.id)

        await self.bot.set_bot_commands(commands)

        self.bot.add_handler(
            MessageHandler(
                download_from_bot,
                filters=pyrogram.filters.command(["download"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                text_download_from_bot,
                filters=pyrogram.filters.command(["text_dl", "text-dl"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                download_with_date_prompt,
                filters=pyrogram.filters.command(["dl"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                forward_messages,
                filters=pyrogram.filters.command(["forward"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                download_forward_media,
                filters=pyrogram.filters.media
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                download_from_link,
                filters=pyrogram.filters.regex(r"^https://t.me.*")
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                set_listen_forward_msg,
                filters=pyrogram.filters.command(["listen_forward"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                help_command,
                filters=pyrogram.filters.command(["help"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                get_info,
                filters=pyrogram.filters.command(["get_info"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                get_channel_url,
                filters=pyrogram.filters.command(["get_url"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                help_command,
                filters=pyrogram.filters.command(["start"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                set_language,
                filters=pyrogram.filters.command(["set_language"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )
        self.bot.add_handler(
            MessageHandler(
                add_filter,
                filters=pyrogram.filters.command(["add_filter"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )

        self.bot.add_handler(
            MessageHandler(
                stop,
                filters=pyrogram.filters.command(["stop"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )

        self.bot.add_handler(
            CallbackQueryHandler(
                on_query_handler, filters=pyrogram.filters.user(self.allowed_user_ids)
            )
        )

        self.client.add_handler(MessageHandler(listen_forward_msg))

        try:
            await send_help_str(self.bot, admin.id)
        except Exception:
            pass

        self.reply_task = _bot.app.loop.create_task(_bot.update_reply_message())

        self.bot.add_handler(
            MessageHandler(
                forward_to_comments,
                filters=pyrogram.filters.command(["forward_to_comments"])
                & pyrogram.filters.user(self.allowed_user_ids),
            )
        )

        add_search_handler(_bot)


_bot = DownloadBot()


async def start_download_bot(
    app: Application,
    client: pyrogram.Client,
    add_download_task: Callable,
    download_chat_task: Callable,
):
    """Start download bot"""
    await _bot.start(app, client, add_download_task, download_chat_task)


async def stop_download_bot():
    """Stop download bot"""
    _bot.update_config()
    _bot.is_running = False
    if _bot.reply_task:
        _bot.reply_task.cancel()
    _bot.stop_task("all")
    if _bot.bot:
        await _bot.bot.stop()


async def send_help_str(client: pyrogram.Client, chat_id):
    """
    Sends a help string to the specified chat ID using the provided client.

    Parameters:
        client (pyrogram.Client): The Pyrogram client used to send the message.
        chat_id: The ID of the chat to which the message will be sent.

    Returns:
        str: The help string that was sent.

    Note:
        The help string includes information about the Telegram Media Downloader bot,
        its version, and the available commands.
    """

    update_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Github",
                    url="https://github.com/tangyoha/telegram_media_downloader/releases",
                ),
                InlineKeyboardButton(
                    "Join us", url="https://t.me/TeegramMediaDownload"
                ),
            ]
        ]
    )
    latest_release_str = ""
    # try:
    #     latest_release = get_latest_release(_bot.app.proxy)

    #     latest_release_str = (
    #         f"{_t('New Version')}: [{latest_release['name']}]({latest_release['html_url']})\an"
    #         if latest_release
    #         else ""
    #     )
    # except Exception:
    #     latest_release_str = ""

    msg = (
        f"`\n🤖 {_t('Telegram Media Downloader')}\n"
        f"🌐 {_t('Version')}: {utils.__version__}`\n"
        f"{latest_release_str}\n"
        f"{_t('Available commands:')}\n"
        f"/help - {_t('Show available commands')}\n"
        f"/get_info - {_t('Get group and user info from message link')}\n"
        f"/download - {_t('Download messages')}\n"
        f"/text_dl - {_t('Download message text or urls')}\n"
        f"/forward - {_t('Forward messages')}\n"
        f"/listen_forward - {_t('Listen for forwarded messages')}\n"
        f"/forward_to_comments - {_t('Forward a specific media to a comment section')}\n"
        f"/set_language - {_t('Set language')}\n"
        f"/stop - {_t('Stop bot download or forward')}\n\n"
        f"{_t('**Note**: 1 means the start of the entire chat')},"
        f"{_t('0 means the end of the entire chat')}\n"
        f"`[` `]` {_t('means optional, not required')}\n"
    )

    await client.send_message(chat_id, msg, reply_markup=update_keyboard)


async def help_command(client: pyrogram.Client, message: pyrogram.types.Message):
    """
    Sends a message with the available commands and their usage.

    Parameters:
        client (pyrogram.Client): The client instance.
        message (pyrogram.types.Message): The message object.

    Returns:
        None
    """

    await send_help_str(client, message.chat.id)


async def set_language(client: pyrogram.Client, message: pyrogram.types.Message):
    """
    Set the language of the bot.

    Parameters:
        client (pyrogram.Client): The pyrogram client.
        message (pyrogram.types.Message): The message containing the command.

    Returns:
        None
    """

    if len(message.text.split()) != 2:
        await client.send_message(
            message.from_user.id,
            _t("Invalid command format. Please use /set_language en/ru/zh/ua"),
        )
        return

    language = message.text.split()[1]

    try:
        language = Language[language.upper()]
        _bot.app.set_language(language)
        await client.send_message(
            message.from_user.id, f"{_t('Language set to')} {language.name}"
        )
    except KeyError:
        await client.send_message(
            message.from_user.id,
            _t("Invalid command format. Please use /set_language en/ru/zh/ua"),
        )


async def get_info(client: pyrogram.Client, message: pyrogram.types.Message):
    """
    Async function that retrieves information from a group message link.
    """

    msg = _t("Invalid command format. Please use /get_info group_message_link")

    args = message.text.split()
    if len(args) != 2:
        await client.send_message(
            message.from_user.id,
            msg,
        )
        return

    try:
        chat_id, message_id, _ = await parse_link(_bot.client, args[1])

        if not chat_id:
            msg = (
                f"{_t('Invalid Telegram link format')}.\n\n"
                f"{_t('Supported formats')}:\n"
                f"• https://t.me/username\n"
                f"• https://t.me/username/123\n"
                f"• https://t.me/c/1234567890/123\n"
            )
            await client.send_message(message.from_user.id, msg)
            return

        entity = None
        entity = await _bot.client.get_chat(chat_id)

        if entity:
            if message_id:
                _message = await retry(_bot.client.get_messages, args=(chat_id, message_id))
                if _message:
                    meta_data = MetaData()
                    set_meta_data(meta_data, _message)
                    msg = (
                        f"`\n"
                        f"{_t('Group/Channel')}\n"
                        f"├─ {_t('id')}: {entity.id}\n"
                        f"├─ {_t('first name')}: {entity.first_name}\n"
                        f"├─ {_t('last name')}: {entity.last_name}\n"
                        f"└─ {_t('name')}: {entity.username}\n"
                        f"{_t('Message')}\n"
                    )

                    for key, value in meta_data.data().items():
                        if key == "send_name":
                            msg += f"└─ {key}: {value or None}\n"
                        else:
                            msg += f"├─ {key}: {value or None}\n"

                    msg += "`"
                else:
                    msg = _t("Message not found or you don't have access to it.")
            else:
                # Show channel/group info without message details
                msg = (
                    f"`\n"
                    f"{_t('Group/Channel')}\n"
                    f"├─ {_t('id')}: {entity.id}\n"
                    f"├─ {_t('first name')}: {entity.first_name}\n"
                    f"├─ {_t('last name')}: {entity.last_name}\n"
                    f"└─ {_t('name')}: {entity.username}\n"
                    f"`"
                )
        else:
            msg = _t("Could not find the chat. Make sure you have access to it.")
    except Exception as e:
        logger.error(f"Error in get_info: {e}")
        msg = (
            f"{_t('Error retrieving information')}.\n"
            f"{_t('Make sure')}:\n"
            f"• {_t('The link is valid')}\n"
            f"• {_t('You have access to the chat')}\n"
            f"• {_t('The bot is a member of the chat (for private groups)')}\n"
        )

    await client.send_message(
        message.from_user.id,
        msg,
    )


async def get_channel_url(client: pyrogram.Client, message: pyrogram.types.Message):
    """
    Get the Telegram URL for a channel/group.
    Usage: /get_url <channel_username or channel_id>
    """

    args = message.text.split()
    if len(args) != 2:
        msg = (
            f"{_t('Invalid command format')}.\n\n"
            f"<b>{_t('Usage')}:</b>\n"
            f"<i>/get_url @channel_username</i>\n"
            f"<i>/get_url channel_username</i>\n"
            f"<i>/get_url -1001234567890</i>\n\n"
            f"<b>{_t('Examples')}:</b>\n"
            f"<i>/get_url @telegram</i>\n"
            f"<i>/get_url telegram</i>\n"
            f"<i>/get_url -1001234567890</i>\n"
        )
        await client.send_message(
            message.from_user.id,
            msg,
            parse_mode=pyrogram.enums.ParseMode.HTML
        )
        return

    channel_input = args[1].strip()

    # Remove @ if present
    if channel_input.startswith("@"):
        channel_input = channel_input[1:]

    try:
        # Get chat info
        entity = await _bot.client.get_chat(channel_input)

        if not entity:
            await client.send_message(
                message.from_user.id,
                _t("Could not find the channel/group. Make sure you have access to it."),
                reply_parameters=_reply_parameters(message),
            )
            return

        # Build the URL based on chat type
        url = None
        chat_type = None

        if entity.username:
            # Public channel/group
            url = f"https://t.me/{entity.username}"
            chat_type = "Public"
        else:
            # Private channel/group - use the numeric ID
            # For private channels, the ID format is -100xxxxxxxxxx
            # We need to remove the -100 prefix to get the channel ID for the URL
            chat_id = str(entity.id)
            if chat_id.startswith("-100"):
                channel_id = chat_id[4:]  # Remove -100 prefix
                url = f"https://t.me/c/{channel_id}/1"
                chat_type = "Private"
            else:
                # Regular group ID
                url = f"https://t.me/c/{chat_id}/1"
                chat_type = "Private"

        msg = (
            f"<b>{_t('Channel/Group Information')}:</b>\n\n"
            f"<b>{_t('Name')}:</b> {entity.title}\n"
            f"<b>{_t('Type')}:</b> {chat_type} {entity.type.value if entity.type else 'Unknown'}\n"
            f"<b>{_t('ID')}:</b> <code>{entity.id}</code>\n"
        )

        if entity.username:
            msg += f"<b>{_t('Username')}:</b> @{entity.username}\n"

        msg += f"\n<b>{_t('URL')}:</b> <code>{url}</code>\n"

        if entity.description:
            desc = entity.description[:200] + "..." if len(entity.description) > 200 else entity.description
            msg += f"\n<b>{_t('Description')}:</b>\n{desc}\n"

        await client.send_message(
            message.from_user.id,
            msg,
            parse_mode=pyrogram.enums.ParseMode.HTML,
            reply_parameters=_reply_parameters(message),
        )

    except Exception as e:
        logger.error(f"Error in get_channel_url: {e}")
        msg = (
            f"{_t('Error retrieving channel information')}.\n\n"
            f"<b>{_t('Possible reasons')}:</b>\n"
            f"• {_t('Channel/group does not exist')}\n"
            f"• {_t('You do not have access to the channel/group')}\n"
            f"• {_t('The bot is not a member of the channel/group')}\n"
            f"• {_t('Invalid channel ID or username')}\n\n"
            f"<b>{_t('Error details')}:</b> {str(e)}\n"
        )
        await client.send_message(
            message.from_user.id,
            msg,
            parse_mode=pyrogram.enums.ParseMode.HTML,
            reply_parameters=_reply_parameters(message),
        )


async def add_filter(client: pyrogram.Client, message: pyrogram.types.Message):
    """
    Set the download filter of the bot.

    Parameters:
        client (pyrogram.Client): The pyrogram client.
        message (pyrogram.types.Message): The message containing the command.

    Returns:
        None
    """

    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        await client.send_message(
            message.from_user.id,
            _t("Invalid command format. Please use /add_filter your filter"),
        )
        return

    filter_str = replace_date_time(args[1])
    res, err = _bot.filter.check_filter(filter_str)
    if res:
        _bot.app.down = args[1]
        await client.send_message(
            message.from_user.id, f"{_t('Add download filter')} : {args[1]}"
        )
    else:
        await client.send_message(
            message.from_user.id, f"{err}\n{_t('Check error, please add again!')}"
        )
    return


async def direct_download(
    download_bot: DownloadBot,
    chat_id: Union[str, int],
    message: pyrogram.types.Message,
    download_message: pyrogram.types.Message,
    client: pyrogram.Client = None,
):
    """Direct Download"""

    replay_message = "Direct download..."
    last_reply_message = await download_bot.bot.send_message(
        message.from_user.id,
        replay_message,
        reply_parameters=_reply_parameters(message),
    )
    _track_bot_status_message(
        _bot.app if download_bot else None,
        message.from_user.id,
        last_reply_message.id,
    )

    node = TaskNode(
        chat_id=chat_id,
        from_user_id=message.from_user.id,
        reply_message_id=last_reply_message.id,
        replay_message=replay_message,
        limit=1,
        bot=download_bot.bot,
        task_id=_bot.gen_task_id(),
    )

    node.client = client

    _bot.add_task_node(node)

    await _bot.add_download_task(
        download_message,
        node,
    )

    node.is_running = True


async def download_forward_media(
    client: pyrogram.Client, message: pyrogram.types.Message
):
    """
    Downloads the media from a forwarded message.

    Parameters:
        client (pyrogram.Client): The client instance.
        message (pyrogram.types.Message): The message object.

    Returns:
        None
    """

    if message.media and getattr(message, message.media.value):
        await direct_download(_bot, message.from_user.id, message, message, client)
        return

    await client.send_message(
        message.from_user.id,
        f"1. {_t('Direct download, directly forward the message to your robot')}\n\n",
        parse_mode=pyrogram.enums.ParseMode.HTML,
    )


async def download_from_link(client: pyrogram.Client, message: pyrogram.types.Message):
    """
    Downloads a single message from a Telegram link.

    Parameters:
        client (pyrogram.Client): The pyrogram client.
        message (pyrogram.types.Message): The message containing the Telegram link.

    Returns:
        None
    """

    if not message.text or not message.text.startswith("https://t.me"):
        return

    msg = (
        f"1. {_t('Directly download a single message')}\n"
        "<i>https://t.me/12000000/1</i>\n\n"
    )

    text = message.text.split()
    if len(text) != 1:
        await client.send_message(
            message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
        )

    chat_id, message_id, _ = await parse_link(_bot.client, text[0])

    entity = None
    if chat_id:
        entity = await _bot.client.get_chat(chat_id)
    if entity:
        if message_id:
            download_message = await retry(
                _bot.client.get_messages, args=(chat_id, message_id)
            )
            if download_message:
                await direct_download(_bot, entity.id, message, download_message)
            else:
                await client.send_message(
                    message.from_user.id,
                    f"{_t('From')} {entity.title} {_t('download')} {message_id} {_t('error')}!",
                    reply_parameters=_reply_parameters(message),
                )
        return

    await client.send_message(
        message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
    )


# pylint: disable = R0912, R0915,R0914


async def download_with_date_prompt(client: pyrogram.Client, message: pyrogram.types.Message):
    """
    Simplified download command that prompts for date range.
    Usage: /dl <link> [start_date] [end_date]
    Example: /dl https://t.me/channel 2024-01-01 2024-12-31
    """

    args = message.text.split()
    help_msg = (
        f"{_t('Download messages with optional date filtering')}:\n\n"
        f"<b>{_t('Usage')}:</b>\n"
        f"<i>/dl https://t.me/channel</i> - {_t('Download all messages')}\n"
        f"<i>/dl https://t.me/channel 2024-01-01</i> - {_t('Download from date onwards')}\n"
        f"<i>/dl https://t.me/channel 2024-01-01 2024-12-31</i> - {_t('Download date range')}\n"
        f"<i>/dl https://t.me/channel images</i> - {_t('Download only image media types')}\n"
        f"<i>/dl https://t.me/channel --ext .epub</i> - {_t('Download only matching extensions')}\n\n"
        f"<b>{_t('Date formats')}:</b>\n"
        f"• YYYY-MM-DD\n"
        f"• YYYY-MM-DD HH:MM:SS\n"
        f"• YYYY-MM\n"
    )

    if len(args) < 2:
        await client.send_message(
            message.from_user.id,
            help_msg,
            parse_mode=pyrogram.enums.ParseMode.HTML
        )
        return

    url = args[1]
    selector_flag, selector_mode, selector_err, remaining = _parse_selector_flags(
        args[2:]
    )
    if selector_err:
        await client.send_message(
            message.from_user.id,
            f"{selector_err}\n\n{help_msg}",
            parse_mode=pyrogram.enums.ParseMode.HTML,
        )
        return

    date_tokens: List[str] = []
    selector_positional = None
    for token in remaining:
        if token and token[0].isdigit():
            date_tokens.append(token)
        elif selector_positional is None:
            selector_positional = token
        else:
            await client.send_message(
                message.from_user.id,
                help_msg,
                parse_mode=pyrogram.enums.ParseMode.HTML,
            )
            return

    if len(date_tokens) > 2:
        await client.send_message(
            message.from_user.id,
            help_msg,
            parse_mode=pyrogram.enums.ParseMode.HTML,
        )
        return

    if selector_flag and selector_positional:
        await client.send_message(
            message.from_user.id,
            f"{_t('Please provide only one selector (positional or flag).')}\n\n{help_msg}",
            parse_mode=pyrogram.enums.ParseMode.HTML,
        )
        return

    selector = selector_flag or selector_positional
    (
        media_types_override,
        file_formats_override,
        extension_filter,
        selector_err,
    ) = _resolve_selector(_bot.app, selector, selector_mode)
    if selector_err:
        await client.send_message(
            message.from_user.id,
            f"{selector_err}\n\n{help_msg}",
            parse_mode=pyrogram.enums.ParseMode.HTML,
        )
        return

    start_date = date_tokens[0] if len(date_tokens) > 0 else None
    end_date = date_tokens[1] if len(date_tokens) > 1 else None

    # Build filter string
    download_filter = None
    if start_date:
        start_date = replace_date_time(start_date)
        download_filter = f"message_date>={start_date}"
        if end_date:
            end_date = replace_date_time(end_date)
            download_filter += f"&message_date<={end_date}"
    if extension_filter:
        if download_filter:
            download_filter = f"{download_filter}&{extension_filter}"
        else:
            download_filter = extension_filter

    # Validate filter if provided
    if download_filter:
        res, err = _bot.filter.check_filter(download_filter)
        if not res:
            await client.send_message(
                message.from_user.id,
                f"{_t('Invalid date format')}. {err}",
                reply_parameters=_reply_parameters(message),
            )
            return

    try:
        chat_id, _, _ = await parse_link(_bot.client, url)
        if not chat_id:
            await client.send_message(
                message.from_user.id,
                _t("Invalid Telegram link. Please provide a valid channel/group link."),
                reply_parameters=_reply_parameters(message),
            )
            return

        entity = await _bot.client.get_chat(chat_id)
        if not entity:
            await client.send_message(
                message.from_user.id,
                _t("Could not access the chat. Make sure the bot has access to it."),
                reply_parameters=_reply_parameters(message),
            )
            return

        chat_title = entity.title
        chat_download_config = ChatDownloadConfig()
        chat_download_config.last_read_message_id = 1
        chat_download_config.download_filter = download_filter

        reply_message = f"from {chat_title} "
        if download_filter:
            reply_message += f"downloading messages with filter: {download_filter}"
        else:
            reply_message += "downloading all messages"

        last_reply_message = await client.send_message(
            message.from_user.id,
            reply_message,
            reply_parameters=_reply_parameters(message),
        )
        _track_bot_status_message(_bot.app, message.from_user.id, last_reply_message.id)

        node = TaskNode(
            chat_id=entity.id,
            from_user_id=message.from_user.id,
            reply_message_id=last_reply_message.id,
            replay_message=reply_message,
            limit=0,
            start_offset_id=1,
            end_offset_id=0,
            bot=_bot.bot,
            task_id=_bot.gen_task_id(),
        )
        node.media_types_override = media_types_override
        node.file_formats_override = file_formats_override
        _bot.add_task_node(node)
        _bot.app.loop.create_task(
            _bot.download_chat_task(_bot.client, chat_download_config, node)
        )

    except Exception as e:
        logger.error(f"Error in download_with_date_prompt: {e}")
        await client.send_message(
            message.from_user.id,
            f"{_t('Error starting download')}:\n{str(e)}",
            reply_parameters=_reply_parameters(message),
        )


async def text_download_from_bot(client: pyrogram.Client, message: pyrogram.types.Message):
    """Download message text or urls from bot"""
    msg = (
        f"{_t('Parameter error, please enter according to the reference format')}:\n\n"
        f"1. {_t('Download message text')}\n"
        "<i>/text_dl https://t.me/channel all non-fiction</i>\n"
        "<i>/text_dl https://t.me/channel all --newest non-fiction</i>\n"
        "<i>/text_dl https://t.me/channel 1 0 non-fiction</i>\n\n"
        f"2. {_t('Download urls only')}\n"
        "<i>/text_dl https://t.me/channel all --urls rapid-links.net</i>\n\n"
        f"3. {_t('Download text and urls')}\n"
        "<i>/text_dl https://t.me/channel all --both non-fiction</i>\n\n"
        f"4. {_t('With date filter')}\n"
        "<i>/text_dl https://t.me/channel all --newest message_date>=2024-01-01 non-fiction</i>\n"
    )

    args = message.text.split()
    if not message.text or len(args) < 3:
        await client.send_message(
            message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
        )
        return

    url = args[1]

    if len(args) >= 3 and args[2].lower() == "all":
        start_offset_id = 1
        end_offset_id = 0
        remaining = args[3:]
    elif len(args) >= 4:
        try:
            start_offset_id = int(args[2])
            end_offset_id = int(args[3])
            remaining = args[4:]
        except Exception:
            await client.send_message(
                message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
            )
            return
    else:
        await client.send_message(
            message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
        )
        return

    newest_first, order_err, remaining = _parse_order_flags(remaining)
    if order_err:
        await client.send_message(
            message.from_user.id, f"{order_err}\n\n{msg}", parse_mode=pyrogram.enums.ParseMode.HTML
        )
        return

    mode, mode_err, remaining = _parse_text_dl_flags(remaining)
    if mode_err:
        await client.send_message(
            message.from_user.id, f"{mode_err}\n\n{msg}", parse_mode=pyrogram.enums.ParseMode.HTML
        )
        return

    download_filter = None
    text_filter = None
    for token in remaining:
        if _is_filter_token(token) and download_filter is None:
            download_filter = token
        elif text_filter is None:
            text_filter = token
        else:
            await client.send_message(
                message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
            )
            return

    if not text_filter:
        await client.send_message(
            message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
        )
        return

    if download_filter:
        download_filter = replace_date_time(download_filter)
        res, err = _bot.filter.check_filter(download_filter)
        if not res:
            await client.send_message(
                message.from_user.id,
                err,
                reply_parameters=_reply_parameters(message),
            )
            return

    try:
        chat_id, _, _ = await parse_link(_bot.client, url)
        if not chat_id:
            await client.send_message(
                message.from_user.id,
                _t("Invalid Telegram link. Please provide a valid channel/group link."),
                reply_parameters=_reply_parameters(message),
            )
            return

        entity = await _bot.client.get_chat(chat_id)
        if not entity:
            await client.send_message(
                message.from_user.id,
                _t("Could not access the chat. Make sure the bot has access to it."),
                reply_parameters=_reply_parameters(message),
            )
            return

        chat_title = entity.title
        chat_download_config = ChatDownloadConfig()
        chat_download_config.last_read_message_id = start_offset_id
        chat_download_config.download_filter = download_filter

        reply_message = f"from {chat_title} "
        if download_filter:
            reply_message += f"downloading text with filter: {download_filter}"
        else:
            reply_message += "downloading text"

        last_reply_message = await client.send_message(
            message.from_user.id,
            reply_message,
            reply_parameters=_reply_parameters(message),
        )
        _track_bot_status_message(_bot.app, message.from_user.id, last_reply_message.id)

        limit = 0
        if end_offset_id:
            if end_offset_id < start_offset_id:
                raise ValueError(
                    f"end_offset_id < start_offset_id, {end_offset_id} < {start_offset_id}"
                )
            limit = end_offset_id - start_offset_id + 1

        node = TaskNode(
            chat_id=entity.id,
            from_user_id=message.from_user.id,
            reply_message_id=last_reply_message.id,
            replay_message=reply_message,
            limit=limit,
            start_offset_id=start_offset_id,
            end_offset_id=end_offset_id,
            bot=_bot.bot,
            task_id=_bot.gen_task_id(),
            download_newest_first=newest_first,
            text_download=True,
            text_filter=text_filter,
            text_output_mode=mode,
        )
        _bot.add_task_node(node)
        _bot.app.loop.create_task(
            _bot.download_chat_task(_bot.client, chat_download_config, node)
        )
    except Exception as e:
        await client.send_message(
            message.from_user.id,
            f"{_t('chat input error, please enter the channel or group link')}\n\n"
            f"{_t('Error type')}: {e.__class__}"
            f"{_t('Exception message')}: {e}",
        )
        return


async def download_from_bot(client: pyrogram.Client, message: pyrogram.types.Message):
    """Download from bot"""

    msg = (
        f"{_t('Parameter error, please enter according to the reference format')}:\n\n"
        f"1. {_t('Download all messages of common group')}\n"
        "<i>/download https://t.me/fkdhlg all</i>\n"
        "<i>/download https://t.me/fkdhlg all --newest</i>\n"
        "<i>/download https://t.me/fkdhlg 1 0</i>\n\n"
        f"{_t('The private group (channel) link is a random group message link')}\n\n"
        f"2. {_t('The download starts from the N message to the end of the M message')}. "
        f"{_t('When M is 0, it means the last message. The filter is optional')}\n"
        f"<i>/download https://t.me/12000000 N M [filter]</i>\n\n"
        f"3. {_t('Download with date filter (messages from specific date)')}\n"
        f"<i>/download https://t.me/channel all --newest message_date>=2024-01-01</i>\n"
        f"<i>/download https://t.me/channel 1 0 message_date>=2024-01-01</i>\n\n"
        f"4. {_t('Download messages within date range')}\n"
        f"<i>/download https://t.me/channel all message_date>=2024-01-01&message_date<=2024-12-31</i>\n"
        f"<i>/download https://t.me/channel 1 0 message_date>=2024-01-01&message_date<=2024-12-31</i>\n\n"
        f"5. {_t('Download only a category or extension')}\n"
        f"<i>/download https://t.me/channel all images</i>\n"
        f"<i>/download https://t.me/channel all --type documents</i>\n"
        f"<i>/download https://t.me/channel all --ext .epub</i>\n\n"
        f"{_t('Date formats supported')}: YYYY-MM-DD, YYYY-MM-DD HH:MM:SS\n"
    )

    args = message.text.split()
    if not message.text or len(args) < 3:
        await client.send_message(
            message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
        )
        return

    url = args[1]

    # Support "all" as a shortcut for "1 0"
    if len(args) >= 3 and args[2].lower() == "all":
        start_offset_id = 1
        end_offset_id = 0
        remaining = args[3:]
    elif len(args) >= 4:
        try:
            start_offset_id = int(args[2])
            end_offset_id = int(args[3])
            remaining = args[4:]
        except Exception:
            await client.send_message(
                message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
            )
            return
    else:
        await client.send_message(
            message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
        )
        return

    newest_first, order_err, remaining = _parse_order_flags(remaining)
    if order_err:
        await client.send_message(
            message.from_user.id, f"{order_err}\n\n{msg}", parse_mode=pyrogram.enums.ParseMode.HTML
        )
        return

    selector_flag, selector_mode, selector_err, remaining = _parse_selector_flags(
        remaining
    )
    if selector_err:
        await client.send_message(
            message.from_user.id,
            f"{selector_err}\n\n{msg}",
            parse_mode=pyrogram.enums.ParseMode.HTML,
        )
        return

    download_filter = None
    selector_positional = None
    for token in remaining:
        if _is_filter_token(token) and download_filter is None:
            download_filter = token
        elif selector_positional is None:
            selector_positional = token
        else:
            await client.send_message(
                message.from_user.id, msg, parse_mode=pyrogram.enums.ParseMode.HTML
            )
            return

    if selector_flag and selector_positional:
        await client.send_message(
            message.from_user.id,
            f"{_t('Please provide only one selector (positional or flag).')}\n\n{msg}",
            parse_mode=pyrogram.enums.ParseMode.HTML,
        )
        return

    selector = selector_flag or selector_positional
    (
        media_types_override,
        file_formats_override,
        extension_filter,
        selector_err,
    ) = _resolve_selector(_bot.app, selector, selector_mode)
    if selector_err:
        await client.send_message(
            message.from_user.id,
            f"{selector_err}\n\n{msg}",
            parse_mode=pyrogram.enums.ParseMode.HTML,
        )
        return

    limit = 0
    if end_offset_id:
        if end_offset_id < start_offset_id:
            raise ValueError(
                f"end_offset_id < start_offset_id, {end_offset_id} < {start_offset_id}"
            )

        limit = end_offset_id - start_offset_id + 1

    if download_filter:
        download_filter = replace_date_time(download_filter)
    if extension_filter:
        if download_filter:
            download_filter = f"{download_filter}&{extension_filter}"
        else:
            download_filter = extension_filter
    if download_filter:
        res, err = _bot.filter.check_filter(download_filter)
        if not res:
            await client.send_message(
                message.from_user.id,
                err,
                reply_parameters=_reply_parameters(message),
            )
            return
    try:
        chat_id, _, _ = await parse_link(_bot.client, url)
        if chat_id:
            entity = await _bot.client.get_chat(chat_id)
        if entity:
            chat_title = entity.title
            reply_message = f"from {chat_title} "
            chat_download_config = ChatDownloadConfig()
            chat_download_config.last_read_message_id = start_offset_id
            chat_download_config.download_filter = download_filter
            reply_message += (
                f"download message id = {start_offset_id} - {end_offset_id} !"
            )
            last_reply_message = await client.send_message(
                message.from_user.id,
                reply_message,
                reply_parameters=_reply_parameters(message),
            )
            _track_bot_status_message(
                _bot.app, message.from_user.id, last_reply_message.id
            )
            node = TaskNode(
                chat_id=entity.id,
                from_user_id=message.from_user.id,
                reply_message_id=last_reply_message.id,
                replay_message=reply_message,
                limit=limit,
                start_offset_id=start_offset_id,
                end_offset_id=end_offset_id,
                bot=_bot.bot,
                task_id=_bot.gen_task_id(),
                download_newest_first=newest_first,
            )
            node.media_types_override = media_types_override
            node.file_formats_override = file_formats_override
            _bot.add_task_node(node)
            _bot.app.loop.create_task(
                _bot.download_chat_task(_bot.client, chat_download_config, node)
            )
    except Exception as e:
        await client.send_message(
            message.from_user.id,
            f"{_t('chat input error, please enter the channel or group link')}\n\n"
            f"{_t('Error type')}: {e.__class__}"
            f"{_t('Exception message')}: {e}",
        )
        return


async def get_forward_task_node(
    client: pyrogram.Client,
    message: pyrogram.types.Message,
    task_type: TaskType,
    src_chat_link: str,
    dst_chat_link: str,
    offset_id: int = 0,
    end_offset_id: int = 0,
    download_filter: str = None,
    reply_comment: bool = False,
):
    """Get task node"""
    limit: int = 0

    if end_offset_id:
        if end_offset_id < offset_id:
            await client.send_message(
                message.from_user.id,
                f" end_offset_id({end_offset_id}) < start_offset_id({offset_id}),"
                f" end_offset_id{_t('must be greater than')} offset_id",
            )
            return None

        limit = end_offset_id - offset_id + 1

    src_chat_id, _, _ = await parse_link(_bot.client, src_chat_link)
    dst_chat_id, target_msg_id, topic_id = await parse_link(_bot.client, dst_chat_link)

    if not src_chat_id or not dst_chat_id:
        logger.info(f"{src_chat_id} {dst_chat_id}")
        await client.send_message(
            message.from_user.id,
            _t("Invalid chat link") + f"{src_chat_id} {dst_chat_id}",
            reply_parameters=_reply_parameters(message),
        )
        return None

    try:
        src_chat = await _bot.client.get_chat(src_chat_id)
        dst_chat = await _bot.client.get_chat(dst_chat_id)
    except Exception as e:
        await client.send_message(
            message.from_user.id,
            f"{_t('Invalid chat link')} {e}",
            reply_parameters=_reply_parameters(message),
        )
        logger.exception(f"get chat error: {e}")
        return None

    me = await client.get_me()
    if dst_chat.id == me.id:
        # TODO: when bot receive message judge if download
        await client.send_message(
            message.from_user.id,
            _t("Cannot be forwarded to this bot, will cause an infinite loop"),
            reply_parameters=_reply_parameters(message),
        )
        return None

    if download_filter:
        download_filter = replace_date_time(download_filter)
        res, err = _bot.filter.check_filter(download_filter)
        if not res:
            await client.send_message(
                message.from_user.id,
                err,
                reply_parameters=_reply_parameters(message),
            )

    last_reply_message = await client.send_message(
        message.from_user.id,
        "Forwarding message, please wait...",
        reply_parameters=_reply_parameters(message),
    )
    _track_bot_status_message(_bot.app, message.from_user.id, last_reply_message.id)

    node = TaskNode(
        chat_id=src_chat.id,
        from_user_id=message.from_user.id,
        upload_telegram_chat_id=dst_chat_id,
        reply_message_id=last_reply_message.id,
        replay_message=last_reply_message.text,
        has_protected_content=src_chat.has_protected_content,
        download_filter=download_filter,
        limit=limit,
        start_offset_id=offset_id,
        end_offset_id=end_offset_id,
        bot=_bot.bot,
        task_id=_bot.gen_task_id(),
        task_type=task_type,
        topic_id=topic_id,
    )

    if target_msg_id and reply_comment:
        node.reply_to_message = await _bot.client.get_discussion_message(
            dst_chat_id, target_msg_id
        )

    _bot.add_task_node(node)

    node.upload_user = _bot.client
    if not dst_chat.type is pyrogram.enums.ChatType.BOT:
        has_permission = await check_user_permission(_bot.client, me.id, dst_chat.id)
        if has_permission:
            node.upload_user = _bot.bot

    if node.upload_user is _bot.client:
        await client.edit_message_text(
            message.from_user.id,
            last_reply_message.id,
            "Note that the robot may not be in the target group,"
            " use the user account to forward",
        )

    return node


# pylint: disable = R0914
async def forward_message_impl(
    client: pyrogram.Client, message: pyrogram.types.Message, reply_comment: bool
):
    """
    Forward message
    """

    async def report_error(client: pyrogram.Client, message: pyrogram.types.Message):
        """Report error"""

        await client.send_message(
            message.from_user.id,
            f"{_t('Invalid command format')}."
            f"{_t('Please use')} "
            "/forward https://t.me/c/src_chat https://t.me/c/dst_chat "
            f"1 400 `[`{_t('Filter')}`]`\n",
        )

    args = message.text.split(maxsplit=5)
    if len(args) < 5:
        await report_error(client, message)
        return

    src_chat_link = args[1]
    dst_chat_link = args[2]

    try:
        offset_id = int(args[3])
        end_offset_id = int(args[4])
    except Exception:
        await report_error(client, message)
        return

    download_filter = args[5] if len(args) > 5 else None

    node = await get_forward_task_node(
        client,
        message,
        TaskType.Forward,
        src_chat_link,
        dst_chat_link,
        offset_id,
        end_offset_id,
        download_filter,
        reply_comment,
    )

    if not node:
        return

    if not node.has_protected_content:
        try:
            async for item in get_chat_history_v2(  # type: ignore
                _bot.client,
                node.chat_id,
                limit=node.limit,
                max_id=node.end_offset_id,
                offset_id=offset_id,
                reverse=True,
            ):
                await forward_normal_content(client, node, item)
                if node.is_stop_transmission:
                    await client.edit_message_text(
                        message.from_user.id,
                        node.reply_message_id,
                        f"{_t('Stop Forward')}",
                    )
                    break
        except Exception as e:
            await client.edit_message_text(
                message.from_user.id,
                node.reply_message_id,
                f"{_t('Error forwarding message')} {e}",
            )
        finally:
            await report_bot_status(client, node, immediate_reply=True)
            node.stop_transmission()
    else:
        await forward_msg(node, offset_id)


async def forward_messages(client: pyrogram.Client, message: pyrogram.types.Message):
    """
    Forwards messages from one chat to another.

    Parameters:
        client (pyrogram.Client): The pyrogram client.
        message (pyrogram.types.Message): The message containing the command.

    Returns:
        None
    """
    return await forward_message_impl(client, message, False)


async def forward_normal_content(
    client: pyrogram.Client, node: TaskNode, message: pyrogram.types.Message
):
    """Forward normal content"""
    forward_ret = ForwardStatus.FailedForward
    if node.download_filter:
        meta_data = MetaData()
        caption = message.caption
        if caption:
            caption = validate_title(caption)
            _bot.app.set_caption_name(node.chat_id, message.media_group_id, caption)
        else:
            caption = _bot.app.get_caption_name(node.chat_id, message.media_group_id)
        set_meta_data(meta_data, message, caption)
        _bot.filter.set_meta_data(meta_data)
        if not _bot.filter.exec(node.download_filter):
            forward_ret = ForwardStatus.SkipForward
            if message.media_group_id:
                node.upload_status[message.id] = UploadStatus.SkipUpload
                await proc_cache_forward(_bot.client, node, message, False)
            await report_bot_forward_status(client, node, forward_ret)
            return

    await upload_telegram_chat_message(
        _bot.client, node.upload_user, _bot.app, node, message
    )


async def forward_msg(node: TaskNode, message_id: int):
    """Forward normal message"""

    chat_download_config = ChatDownloadConfig()
    chat_download_config.last_read_message_id = message_id
    chat_download_config.download_filter = node.download_filter  # type: ignore

    await _bot.download_chat_task(_bot.client, chat_download_config, node)


async def set_listen_forward_msg(
    client: pyrogram.Client, message: pyrogram.types.Message
):
    """
    Set the chat to listen for forwarded messages.

    Args:
        client (pyrogram.Client): The pyrogram client.
        message (pyrogram.types.Message): The message sent by the user.

    Returns:
        None
    """
    args = message.text.split(maxsplit=3)

    if len(args) < 3:
        await client.send_message(
            message.from_user.id,
            f"{_t('Invalid command format')}. {_t('Please use')} /listen_forward "
            f"https://t.me/c/src_chat https://t.me/c/dst_chat [{_t('Filter')}]\n",
        )
        return

    src_chat_link = args[1]
    dst_chat_link = args[2]

    download_filter = args[3] if len(args) > 3 else None

    node = await get_forward_task_node(
        client,
        message,
        TaskType.ListenForward,
        src_chat_link,
        dst_chat_link,
        download_filter=download_filter,
    )

    if not node:
        return

    if node.chat_id in _bot.listen_forward_chat:
        _bot.remove_task_node(_bot.listen_forward_chat[node.chat_id].task_id)

    node.is_running = True
    _bot.listen_forward_chat[node.chat_id] = node


async def listen_forward_msg(client: pyrogram.Client, message: pyrogram.types.Message):
    """
    Forwards messages from a chat to another chat if the message does not contain protected content.
    If the message contains protected content, it will be downloaded and forwarded to the other chat.

    Parameters:
        client (pyrogram.Client): The pyrogram client.
        message (pyrogram.types.Message): The message to be forwarded.
    """

    if message.chat and message.chat.id in _bot.listen_forward_chat:
        node = _bot.listen_forward_chat[message.chat.id]

        # TODO(tangyoha):fix run time change protected content
        if not node.has_protected_content:
            await forward_normal_content(client, node, message)
            await report_bot_status(client, node, immediate_reply=True)
        else:
            await _bot.add_download_task(
                message,
                node,
            )


async def stop(client: pyrogram.Client, message: pyrogram.types.Message):
    """Stops listening for forwarded messages."""

    await client.send_message(
        message.chat.id,
        _t("Please select:"),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        _t("Stop Download"), callback_data="stop_download"
                    ),
                    InlineKeyboardButton(
                        _t("Stop Forward"), callback_data="stop_forward"
                    ),
                ],
                [  # Second row
                    InlineKeyboardButton(
                        _t("Stop Listen Forward"), callback_data="stop_listen_forward"
                    )
                ],
            ]
        ),
    )


async def stop_task(
    client: pyrogram.Client,
    query: pyrogram.types.CallbackQuery,
    queryHandler: str,
    task_type: TaskType,
):
    """Stop task"""
    if query.data == queryHandler:
        buttons: List[InlineKeyboardButton] = []
        temp_buttons: List[InlineKeyboardButton] = []
        for key, value in _bot.task_node.copy().items():
            if not value.is_finish() and value.task_type is task_type:
                if len(temp_buttons) == 3:
                    buttons.append(temp_buttons)
                    temp_buttons = []
                temp_buttons.append(
                    InlineKeyboardButton(
                        f"{key}", callback_data=f"{queryHandler} task {key}"
                    )
                )
        if temp_buttons:
            buttons.append(temp_buttons)

        if buttons:
            buttons.insert(
                0,
                [
                    InlineKeyboardButton(
                        _t("all"), callback_data=f"{queryHandler} task all"
                    )
                ],
            )
            await client.edit_message_text(
                query.message.from_user.id,
                query.message.id,
                f"{_t('Stop')} {_t(task_type.name)}...",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        else:
            await client.edit_message_text(
                query.message.from_user.id,
                query.message.id,
                f"{_t('No Task')}",
            )
    else:
        task_id = query.data.split(" ")[2]
        await client.edit_message_text(
            query.message.from_user.id,
            query.message.id,
            f"{_t('Stop')} {_t(task_type.name)}...",
        )
        _bot.stop_task(task_id)


async def on_query_handler(
    client: pyrogram.Client, query: pyrogram.types.CallbackQuery
):
    """
    Asynchronous function that handles query callbacks.

    Parameters:
        client (pyrogram.Client): The Pyrogram client object.
        query (pyrogram.types.CallbackQuery): The callback query object.

    Returns:
        None
    """

    for it in QueryHandler:
        queryHandler = QueryHandlerStr.get_str(it.value)
        if queryHandler in query.data:
            await stop_task(client, query, queryHandler, TaskType(it.value))


async def forward_to_comments(client: pyrogram.Client, message: pyrogram.types.Message):
    """
    Forwards specified media to a designated comment section.

    Usage: /forward_to_comments <source_chat_link> <destination_chat_link> <msg_start_id> <msg_end_id>

    Parameters:
        client (pyrogram.Client): The pyrogram client.
        message (pyrogram.types.Message): The message containing the command.
    """
    return await forward_message_impl(client, message, True)
