
<h1 align="center">Telegram Media Downloader</h1>

<p align="center">
<a href="https://github.com/tangyoha/telegram_media_downloader/actions"><img alt="Unittest" src="https://github.com/tangyoha/telegram_media_downloader/workflows/Unittest/badge.svg"></a>
<a href="https://codecov.io/gh/tangyoha/telegram_media_downloader"><img alt="Coverage Status" src="https://codecov.io/gh/tangyoha/telegram_media_downloader/branch/master/graph/badge.svg"></a>
<a href="https://github.com/tangyoha/telegram_media_downloader/blob/master/LICENSE"><img alt="License: MIT" src="https://black.readthedocs.io/en/stable/_static/license.svg"></a>
<a href="https://github.com/python/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
<a href="https://github.com/tangyoha/telegram_media_downloader/releases">
<img alt="Code style: black" src="https://img.shields.io/github/v/release/tangyoha/telegram_media_downloader?display_name=tag"></a>
</p>

<h3 align="center">
  <a href="./README_CN.md">中文</a><span> · </span>
  <a href="https://github.com/tangyoha/telegram_media_downloader/discussions/categories/ideas">Feature request</a>
  <span> · </span>
  <a href="https://github.com/tangyoha/telegram_media_downloader/issues">Report a bug</a>
  <span> · </span>
  Support: <a href="https://github.com/tangyoha/telegram_media_downloader/discussions">Discussions</a>
  <span> & </span>
  <a href="https://t.me/TeegramMediaDownload">Telegram Community</a>
</h3>

## Overview
> Support two default running

* The robot is running, and the command `download` or `forward` is issued from the robot

* Download as a one-time download tool

### UI

#### Web page

> After running, open a browser and visit `localhost:5000`
> If it is a remote machine, you need to configure web_host: 0.0.0.0


<img alt="Code style: black" style="width:100%; high:60%;" src="./screenshot/web_ui.gif"/>

### Robot

> Need to configure bot_token, please refer to [Documentation](https://github.com/tangyoha/telegram_media_downloader/wiki/How-to-Download-Using-Robots)

<img alt="Code style: black" style="width:60%; high:30%; " src="./screenshot/bot.gif"/>

### Support

| Category             | Support                                          |
| -------------------- | ------------------------------------------------ |
| Language             | `Python 3.7` and above                           |
| Download media types | audio, document, photo, video, video_note, voice |

### Version release plan

* [v2.2.0](https://github.com/tangyoha/telegram_media_downloader/issues/2)

## Installation

For *nix os distributions with `make` availability

```sh
git clone https://github.com/tangyoha/telegram_media_downloader.git
cd telegram_media_downloader
make install
```

For Windows which doesn't have `make` inbuilt

```sh
git clone https://github.com/tangyoha/telegram_media_downloader.git
cd telegram_media_downloader
pip3 install -r requirements.txt
```

## Docker
> For more detailed installation tutorial, please check the wiki

Make sure you have **docker** and **docker-compose** installed
```sh
docker pull tangyoha/telegram_media_downloader:latest
mkdir -p ~/app && mkdir -p ~/app/log/ && cd ~/app
wget https://raw.githubusercontent.com/tangyoha/telegram_media_downloader/master/docker-compose.yaml -O docker-compose.yaml
wget https://raw.githubusercontent.com/tangyoha/telegram_media_downloader/master/config.yaml -O config.yaml
wget https://raw.githubusercontent.com/tangyoha/telegram_media_downloader/master/data.yaml -O data.yaml
# vi config.yaml and docker-compose.yaml
vi config.yaml

# The first time you need to start the foreground
# enter your phone number and code, then exit(ctrl + c)
docker-compose run --rm telegram_media_downloader

# After performing the above operations, all subsequent startups will start in the background
docker-compose up -d

# Upgrade
docker pull tangyoha/telegram_media_downloader:latest
cd ~/app
docker-compose down
docker-compose up -d
```

## Upgrade installation

```sh
cd telegram_media_downloader
pip3 install -r requirements.txt
```

## Configuration

All the configurations are  passed to the Telegram Media Downloader via `config.yaml` file.

**Getting your API Keys:**
The very first step requires you to obtain a valid Telegram API key (API id/hash pair):

1. Visit  [https://my.telegram.org/apps](https://my.telegram.org/apps)  and log in with your Telegram Account.
2. Fill out the form to register a new Telegram application.
3. Done! The API key consists of two parts:  **api_id**  and  **api_hash**.

**Getting chat id:**

**1. Using web telegram:**

1. Open <https://web.telegram.org/?legacy=1#/im>

2. Now go to the chat/channel and you will see the URL as something like
   - `https://web.telegram.org/?legacy=1#/im?p=u853521067_2449618633394` here `853521067` is the chat id.
   - `https://web.telegram.org/?legacy=1#/im?p=@somename` here `somename` is the chat id.
   - `https://web.telegram.org/?legacy=1#/im?p=s1301254321_6925449697188775560` here take `1301254321` and add `-100` to the start of the id => `-1001301254321`.
   - `https://web.telegram.org/?legacy=1#/im?p=c1301254321_6925449697188775560` here take `1301254321` and add `-100` to the start of the id => `-1001301254321`.

**2. Using bot:**

1. Use [@username_to_id_bot](https://t.me/username_to_id_bot) to get the chat_id of
    - almost any telegram user: send username to the bot or just forward their message to the bot
    - any chat: send chat username or copy and send its joinchat link to the bot
    - public or private channel: same as chats, just copy and send to the bot
    - id of any telegram bot

### config.yaml

```yaml
api_hash: your_api_hash
api_id: your_api_id
chat:
- chat_id: telegram_chat_id
  last_read_message_id: 0
  download_filter: message_date >= 2022-12-01 00:00:00 and message_date <= 2023-01-17 00:00:00
- chat_id: telegram_chat_id_2
  last_read_message_id: 0
# note we remove ids_to_retry to data.yaml
ids_to_retry: []
media_types:
- audio
- document
- photo
- video
- voice
- animation #gif
file_formats:
  audio:
  - all
  document:
  - pdf
  - epub
  video:
  - mp4
save_path: D:\telegram_media_downloader
file_path_prefix:
- chat_title
- media_datetime
upload_drive:
  # required
  enable_upload_file: true
  # required
  remote_dir: drive:/telegram
  # required
  upload_adapter: rclone
  # option,when config upload_adapter rclone then this config are required
  rclone_path: D:\rclone\rclone.exe
  # option
  before_upload_file_zip: True
  # option
  after_upload_file_delete: True
hide_file_name: true
file_name_prefix:
- message_id
- file_name
file_name_prefix_split: ' - '
max_download_task: 5
web_host: 127.0.0.1
web_port: 5000
language: EN
web_login_secret: 123
allowed_user_ids:
- 'me'
date_format: '%Y_%m'
enable_download_txt: false
```

- **api_hash**  - The api_hash you got from telegram apps
- **api_id** - The api_id you got from telegram apps
- **bot_token** - Your bot token
- **chat** - Chat list
  - `chat_id` -  The id of the chat/channel you want to download media. Which you get from the above-mentioned steps.
  - `download_filter` - Download filter, see [How to use Filter](https://github.com/tangyoha/telegram_media_downloader/wiki/How-to-use-Filter)
  - `last_read_message_id` - If it is the first time you are going to read the channel let it be `0` or if you have already used this script to download media it will have some numbers which are auto-updated after the scripts successful execution. Don't change it.
  - `ids_to_retry` - `Leave it as it is.` This is used by the downloader script to keep track of all skipped downloads so that it can be downloaded during the next execution of the script.
- **media_types** - Type of media to download, you can update which type of media you want to download it can be one or any of the available types.
- **file_formats** - File types to download for supported media types which are `audio`, `document` and `video`. Default format is `all`, downloads all files.
- **save_path** - The root directory where you want to store downloaded files.
- **file_path_prefix** - Store file subfolders, the order of the list is not fixed, can be randomly combined.
  - `chat_title`      - Channel or group title, it will be chat id if not exist title.
  - `media_datetime`  - Media date.
  - `media_type`      - Media type, also see `media_types`.
- **upload_drive** - You can upload file to cloud drive.
  - `enable_upload_file` - Enable upload file, default `false`.
  - `remote_dir` - Where you upload, like `drive_id/drive_name`.
  - `upload_adapter` - Upload file adapter, which can be `rclone`, `aligo`. If it is `rclone`, it supports all `rclone` servers that support uploading. If it is `aligo`, it supports uploading `Ali cloud disk`.
  - `rclone_path` - RClone exe path, see [How to use rclone](https://github.com/tangyoha/telegram_media_downloader/wiki/Rclone)
  - `before_upload_file_zip` - Zip file before upload, default `false`.
  - `after_upload_file_delete` - Delete file after upload success, default `false`.
- **file_name_prefix** - Custom file name, use the same as **file_path_prefix**
  - `message_id` - Message id
  - `file_name` - File name (may be empty)
  - `caption` - The title of the message (may be empty)
- **file_name_prefix_split** - Custom file name prefix symbol, the default is `-`
- **max_download_task** - The maximum number of task download tasks, the default is 5.
- **hide_file_name** - Whether to hide the web interface file name, default `false`
- **web_host** - Web host
- **web_port** - Web port
- **language** - Application language, the default is English (`EN`), optional `ZH`(Chinese),`RU`,`UA`
- **web_login_secret** - Web page login password, if not configured, no login is required to access the web page
- **log_level** - see `logging._nameToLevel`.
- **forward_limit** - Limit the number of forwards per minute, the default is 33, please do not modify this parameter by default.
- **allowed_user_ids** - Who is allowed to use the robot? The default login account can be used. Please add single quotes to the name with @.
- **date_format** Support custom configuration of media_datetime format in file_path_prefix.see [python-datetime](https://docs.python.org/3/library/datetime.html)
- **enable_download_txt** Enable download txt file, default `false`
- **download_timeout** Download timeout in seconds (0 = no timeout). Recommended: 300-600 for large files. Default: 600 seconds. See [Timeout Configuration](#timeout-configuration)

## Bot Commands

When using the bot (via `bot_token`), the following commands are available:

### Information Commands

**`/get_info <telegram_link>`** - Get detailed information about a message or channel
```
/get_info https://t.me/channel
/get_info https://t.me/channel/123
/get_info https://t.me/c/1234567890/123
```

**`/get_url <username_or_id>`** - Get the Telegram URL for a channel/group
```
/get_url @telegram
/get_url telegram
/get_url -1001234567890
```

### Download Commands

**`/download <link> <start> <end> [filter]`** - Download messages with full control

Examples:
```
# Download all messages (using "all" shortcut)
/download https://t.me/channel all

# Download all messages (traditional syntax)
/download https://t.me/channel 1 0

# Download specific message range
/download https://t.me/channel 100 200

# Download all with date filter
/download https://t.me/channel all message_date>=2024-01-01

# Download from date to now
/download https://t.me/channel 1 0 message_date>=2024-01-01

# Download date range
/download https://t.me/channel all message_date>=2024-01-01&message_date<=2024-12-31
```

**`/dl <link> [start_date] [end_date]`** - Simplified download with date filtering

Examples:
```
# Download all messages
/dl https://t.me/channel

# Download from date onwards
/dl https://t.me/channel 2024-01-01

# Download date range
/dl https://t.me/channel 2024-01-01 2024-12-31
```

### Other Commands

- **`/help`** - Show help message
- **`/forward`** - Forward messages to another chat
- **`/listen_forward`** - Set up automatic forwarding
- **`/add_filter`** - Add download filter
- **`/set_language`** - Change bot language (EN/ZH/RU/UA)
- **`/stop`** - Stop current download or forward task

## Timeout Configuration

⚠️ **IMPORTANT:** The timeout feature is currently disabled due to compatibility issues with Pyrogram's progress callbacks.

```yaml
# Download timeout in seconds (0 = no timeout)
# NOTE: Currently set to 0 (disabled) due to compatibility issues
download_timeout: 0
```

**Status:** Downloads use Pyrogram's default timeout behavior. The 3-retry mechanism still works for handling errors.

See `docs/TIMEOUT-ISSUE.md` for details and workarounds.

## Date Filtering

Both `/download` and `/dl` commands support date filtering:

### Supported Date Formats
- `YYYY-MM-DD` (e.g., 2024-01-01)
- `YYYY-MM-DD HH:MM:SS` (e.g., 2024-01-01 14:30:00)
- `YYYY-MM` (e.g., 2024-01)

### Filter Syntax (for `/download` command)
```
message_date>=2024-01-01              # From date onwards
message_date<=2024-12-31              # Up to date
message_date>=2024-01-01&message_date<=2024-12-31  # Date range
```

### Examples
```bash
# Download messages from January 2024 onwards
/download https://t.me/channel all message_date>=2024-01-01

# Download messages from 2024
/dl https://t.me/channel 2024-01-01 2024-12-31

# Download messages from specific month
/download https://t.me/channel all message_date>=2024-01-01&message_date<=2024-01-31
```

## Execution

```sh
python3 media_downloader.py
```

All downloaded media will be stored at the root of `save_path`.
The specific location reference is as follows:

The complete directory of video download is: `save_path`/`chat_title`/`media_datetime`/`media_type`.
The order of the list is not fixed and can be randomly combined.
If the configuration is empty, all files are saved under `save_path`.

## Proxy

`socks4, socks5, http` proxies are supported in this project currently. To use it, add the following to the bottom of your `config.yaml` file

```yaml
proxy:
  scheme: socks5
  hostname: 127.0.0.1
  port: 1234
  username: your_username(delete the line if none)
  password: your_password(delete the line if none)
```

If your proxy doesn't require authorization you can omit username and password. Then the proxy will automatically be enabled.

## Quick Reference

### Common Bot Commands

```bash
# Get channel URL
/get_url @channelname

# Get message info
/get_info https://t.me/channel/123

# Download all messages (NEW shortcut!)
/download https://t.me/channel all

# Download all messages (old way still works)
/download https://t.me/channel 1 0

# Download with date filter
/download https://t.me/channel all message_date>=2024-01-01

# Simplified download from date
/dl https://t.me/channel 2024-01-01

# Download date range
/dl https://t.me/channel 2024-01-01 2024-12-31
```

### Configuration Snippets

**Basic config.yaml:**
```yaml
api_hash: your_api_hash
api_id: your_api_id
bot_token: your_bot_token  # Optional, for bot mode
save_path: /path/to/downloads
download_timeout: 600  # 10 minutes (recommended)

media_types:
  - audio
  - document
  - photo
  - video
  - voice

file_formats:
  audio: [all]
  document: [all]
  video: [all]
```

**With cleanup (auto-delete downloaded messages):**
```yaml
cleanup:
  enabled: true
  idle_hours: 3
  delete_skipped_messages: true
  delete_bot_status: false
```

**With date filter in chat config:**
```yaml
chat:
  - chat_id: @yourchannel
    last_read_message_id: 0
    download_filter: date >= 2024-01-01 00:00:00 and date <= 2024-12-31 23:59:59
```

## Recent Improvements

### v2.2.2 (Latest)

**Bug Fixes:**
- ✅ **Automatic TypeError fallback** - PDFs/documents now download successfully despite Pyrogram bug
- ✅ Fixed `/get_info` command crashes with invalid URLs
- ✅ Fixed timeout errors during downloads (proper asyncio timeout handling)
- ✅ Improved link parsing validation

**New Features:**
- ✨ **Automatic recovery** - Downloads retry without progress callback if TypeError occurs
- ✨ **`/get_url` command** - Get Telegram URL for any channel by username or ID
- ✨ **`/dl` command** - Simplified download with easy date filtering
- ✨ **"all" shortcut** - Use `/download <link> all` instead of `/download <link> 1 0`
- ✨ **Configurable timeout** - Set `download_timeout` in config.yaml
- ✨ **Better error messages** - Clear, actionable error messages with suggestions

**Documentation:**
- 📚 `docs/download-improvements.md` - Complete feature documentation
- 📚 `docs/timeout-fix.md` - Timeout configuration guide
- 📚 `docs/new-commands-reference.md` - Quick command reference
- 📚 `docs/FIXES-SUMMARY.md` - Summary of all changes

See the `docs/` folder for detailed documentation on all new features.

## Troubleshooting

### Download Timeouts

If you see timeout errors:
```
ERROR - Message[17]: Timing out after 3 retries, download skipped.
```

**Solution:**
1. Increase `download_timeout` in config.yaml:
   ```yaml
   download_timeout: 1200  # 20 minutes
   ```
2. Reduce concurrent downloads:
   ```yaml
   max_download_task: 3
   max_concurrent_transmissions: 1
   ```

See `docs/timeout-fix.md` for detailed troubleshooting.

### Invalid Link Errors

If `/get_info` or downloads fail with link errors:

**Supported formats:**
- `https://t.me/username` - Public channel/group
- `https://t.me/username/123` - Public channel with message
- `https://t.me/c/1234567890/123` - Private channel (numeric ID)

**Not supported:**
- Links with usernames in private channel format
- Invalid or malformed URLs

Use `/get_url` to get the correct link format for any channel.

## Contributing

### Contributing Guidelines

Read through our [contributing guidelines](https://github.com/tangyoha/telegram_media_downloader/blob/master/CONTRIBUTING.md) to learn about our submission process, coding rules and more.

### Want to Help?

Want to file a bug, contribute some code, or improve documentation? Excellent! Read up on our guidelines for [contributing](https://github.com/tangyoha/telegram_media_downloader/blob/master/CONTRIBUTING.md).

### Code of Conduct

Help us keep Telegram Media Downloader open and inclusive. Please read and follow our [Code of Conduct](https://github.com/tangyoha/telegram_media_downloader/blob/master/CODE_OF_CONDUCT.md).


### Sponsor

[PayPal](https://paypal.me/tangyoha?country.x=C2&locale.x=zh_XC)

<p>
<img alt="Code style: black" style="width:30%" src="./screenshot/alipay.JPG">
<img alt="Code style: black" style="width:30%" src="./screenshot/wechat.JPG">
</p>
