# Complete Command Syntax Reference

> **Last Updated:** After adding "all" shortcut feature

## Quick Answer to Your Questions

### ✅ CORRECT Syntax Options

**Option 1: Using `/download` with filter syntax**
```bash
/download https://t.me/channel all message_date>=2024-01-01&message_date<=2024-12-31
/download https://t.me/channel 1 0 message_date>=2024-01-01&message_date<=2024-12-31
```
Both work! "all" is just a shortcut for "1 0"

**IMPORTANT:** Use `message_date`, not just `date` in filters!

**Option 2: Using `/dl` with simple dates**
```bash
/dl https://t.me/channel 2024-01-01 2024-12-31
```

### ❌ WRONG - This does NOT work
```bash
/download https://t.me/channel 1 0 2024-01-01 2024-12-31
```
The `/download` command expects a **filter string**, not separate date arguments.

---

## Complete `/download` Command Syntax

```
/download <link> all [filter] [selector]
/download <link> <start> <end> [filter] [selector]
```

### Parameters

| Parameter | Required | Description | Examples |
|-----------|----------|-------------|----------|
| `<link>` | ✅ Yes | Telegram channel/group link | `https://t.me/channel` |
| `<start\|all>` | ✅ Yes | Start message ID or "all" | `1`, `100`, `all` |
| `<end>` | ✅ Yes* | End message ID (0 = last) | `0`, `200` |
| `[filter]` | ⬜ Optional | Filter expression | `message_date>=2024-01-01` |
| `[selector]` | ⬜ Optional | Category or extension selector | `images`, `.epub` |

*Note: When using "all", do not provide `<end>`; it is implied as `0` (last message).
Filters must be a single token (no spaces). Use `message_date` in bot commands.
Selectors can be positional (`images`, `.epub`) or flags (`--type`, `--ext`), but only one selector is allowed.

---

## Complete `/text_dl` Command Syntax

```
/text_dl <link> all [filter] [--text|--urls|--both] <match>
/text_dl <link> <start> <end> [filter] [--text|--urls|--both] <match>
```

### Parameters
| Parameter | Required | Description | Examples |
|-----------|----------|-------------|----------|
| `<link>` | ✅ Yes | Telegram channel/group link | `https://t.me/channel` |
| `<start|all>` | ✅ Yes | Start message ID or "all" | `1`, `100`, `all` |
| `<end>` | ✅ Yes* | End message ID (0 = last) | `0`, `200` |
| `[filter]` | ⬜ Optional | Filter expression (same as /download) | `message_date>=2024-01-01` |
| `[--text|--urls|--url|--both]` | ⬜ Optional | Output mode (`--text` default) | `--urls` |
| `<match>` | ✅ Yes | Case-insensitive substring to match | `non-fiction` |

*Note: When using "all", do not provide `<end>`; it is implied as `0` (last message).
`<match>` must be a single token (no spaces).

### Examples - Text and URL Extraction

```bash
# Download all matching text (default text-only)
/text_dl https://t.me/channel all non-fiction

# Download only URLs that contain a pattern
/text_dl https://t.me/channel all --urls rapid-links.net

# Download text with date filtering
/text_dl https://t.me/channel all message_date>=2024-01-01 non-fiction

# Download text + urls for a message range
/text_dl https://t.me/channel 100 200 --both non-fiction
```

### Notes
- Output is appended to a single text file per `file_path_prefix` path.
- `/text_dl` writes even if `enable_download_txt: false` in config.

### Examples - All Messages (/download)

```bash
# NEW: Using "all" shortcut (easiest!)
/download https://t.me/channel all

# Old way (still works)
/download https://t.me/channel 1 0
```

### Examples - Category or Extension Selector
```bash
# Category selector (uses config grouping)
/download https://t.me/channel all images
/download https://t.me/channel all --type documents

# Extension selector (bypasses config file_formats)
/download https://t.me/channel all .epub
/download https://t.me/channel all --ext .epub
```

### Examples - With Date Filters

```bash
# From 2024-01-01 onwards (NEW "all" shortcut)
/download https://t.me/channel all message_date>=2024-01-01

# Date range (NEW "all" shortcut)
/download https://t.me/channel all message_date>=2024-01-01&message_date<=2024-12-31

# Old way (still works)
/download https://t.me/channel 1 0 message_date>=2024-01-01&message_date<=2024-12-31
```

### Examples - Specific Message Ranges

```bash
# Download messages 100 to 200
/download https://t.me/channel 100 200

# Download from message 500 to end
/download https://t.me/channel 500 0

# Download messages 100-200 from 2024 only
/download https://t.me/channel 100 200 message_date>=2024-01-01&message_date<=2024-12-31
```

---

## Complete `/dl` Command Syntax

```
/dl <link> [start_date] [end_date] [selector]
/dl <link> [start_date] [end_date] [--type <category>|--ext <ext>]
```

### Parameters

| Parameter | Required | Description | Examples |
|-----------|----------|-------------|----------|
| `<link>` | ✅ Yes | Telegram channel/group link | `https://t.me/channel` |
| `[start_date]` | ⬜ Optional | Start date (from this date onwards) | `2024-01-01` |
| `[end_date]` | ⬜ Optional | End date | `2024-12-31` |
| `[selector]` | ⬜ Optional | Category or extension selector | `images`, `.epub` |

*Note: Bot commands split on spaces, so `YYYY-MM-DD HH:MM:SS` is not supported here.
Use `config.yaml` filters for time precision. If combining dates and selectors,
prefer `--type/--ext` flags to avoid ambiguity.

### Examples

```bash
# All messages
/dl https://t.me/channel

# From 2024-01-01 to NOW
/dl https://t.me/channel 2024-01-01

# From 2024-01-01 to 2024-12-31
/dl https://t.me/channel 2024-01-01 2024-12-31

# Category selector
/dl https://t.me/channel images

# Extension selector
/dl https://t.me/channel --ext .epub
```

---

## Date Filter Syntax (for `/download` command only)

**Note:** Bot commands require filters to be a single token (no spaces) and use
`message_date` (not `date`) as the field name.

### Operators

- `>=` - Greater than or equal to
- `<=` - Less than or equal to
- `>` - Greater than
- `<` - Less than
- `==` - Equal to

### Combining Conditions

Use `&` (ampersand) to combine conditions:

```bash
# Date range
message_date>=2024-01-01&message_date<=2024-12-31

# Multiple conditions (advanced)
message_date>=2024-01-01&file_size>1000000
```

### Date Formats Supported

| Format | Example | Description |
|--------|---------|-------------|
| `YYYY-MM-DD` | `2024-01-01` | Year-Month-Day |
| `YYYY-MM-DD HH:MM:SS` | `2024-01-01 14:30:00` | With time (use `config.yaml` filters) |
| `YYYY-MM` | `2024-01` | Year-Month only |

---

## "2024-01-01 to NOW" - How to Do It

### Option 1: Using `/download` (NEW shortcut)
```bash
/download https://t.me/channel all message_date>=2024-01-01
```

Just omit the `message_date<=` part! This downloads from 2024-01-01 to the present.

### Option 2: Using `/dl`
```bash
/dl https://t.me/channel 2024-01-01
```

Just omit the second date! This downloads from 2024-01-01 to the present.

### Option 3: Old `/download` syntax
```bash
/download https://t.me/channel 1 0 message_date>=2024-01-01
```

Still works!

---

## Quick Comparison Table

| Task | `/download` (NEW with "all") | `/download` (old way) | `/dl` |
|------|------------------------------|----------------------|-------|
| All messages | `/download URL all` | `/download URL 1 0` | `/dl URL` |
| From date to now | `/download URL all message_date>=2024-01-01` | `/download URL 1 0 message_date>=2024-01-01` | `/dl URL 2024-01-01` |
| Date range | `/download URL all message_date>=2024-01-01&message_date<=2024-12-31` | `/download URL 1 0 message_date>=...` | `/dl URL 2024-01-01 2024-12-31` |
| Specific msg range | `/download URL 100 200` | `/download URL 100 200` | ❌ Not supported |

---

## Real-World Examples

### Example 1: Backup Entire Channel
```bash
# Easiest way (NEW!)
/download https://t.me/mychannel all

# Or use /dl
/dl https://t.me/mychannel
```

### Example 2: Download 2024 Messages Only
```bash
# Using /download (NEW shortcut)
/download https://t.me/mychannel all message_date>=2024-01-01&message_date<=2024-12-31

# Using /dl (simpler)
/dl https://t.me/mychannel 2024-01-01 2024-12-31
```

### Example 3: Download January 2024
```bash
# Using /download (NEW shortcut)
/download https://t.me/mychannel all message_date>=2024-01-01&message_date<=2024-01-31

# Using /dl
/dl https://t.me/mychannel 2024-01-01 2024-01-31

# Using month format
/dl https://t.me/mychannel 2024-01
```

### Example 4: Download Last 1000 Messages
```bash
# NOT possible with /dl (it always downloads all or by date)

# Use /download with message IDs
# First, find out the latest message ID (e.g., 5000)
/download https://t.me/mychannel 4000 5000
```

### Example 5: Archive from Start of 2024 to Today
```bash
# Using /download (NEW shortcut)
/download https://t.me/mychannel all message_date>=2024-01-01

# Using /dl (simpler!)
/dl https://t.me/mychannel 2024-01-01
```

---

## Common Mistakes

### ❌ WRONG
```bash
# This does NOT work - /download expects filter syntax, not date args
/download https://t.me/channel 1 0 2024-01-01 2024-12-31

# This does NOT work - missing message IDs
/download https://t.me/channel message_date>=2024-01-01

# This does NOT work - wrong field name (use message_date, not date)
/download https://t.me/channel all date>=2024-01-01
```

### ✅ CORRECT
```bash
# Use "all" or "1 0" with filter syntax (IMPORTANT: use message_date)
/download https://t.me/channel all message_date>=2024-01-01&message_date<=2024-12-31
/download https://t.me/channel 1 0 message_date>=2024-01-01&message_date<=2024-12-31

# Or use /dl with simple dates
/dl https://t.me/channel 2024-01-01 2024-12-31
```

---

## Tips

1. **Use "all" shortcut** - It's easier than typing "1 0"
   ```bash
   /download URL all
   ```

2. **Use `/dl` for simple date filtering** - Much easier syntax
   ```bash
   /dl URL 2024-01-01
   ```

3. **Use `/download` for complex needs** - When you need specific message ranges
   ```bash
   /download URL 100 200 message_date>=2024-01-01
   ```

4. **Get the channel URL first** if you're unsure
   ```bash
   /get_url @channelname
   ```

5. **Test with a small range first**
   ```bash
   /download URL 1 10  # Just first 10 messages
   ```

---

## Still Confused?

**Rule of thumb:**
- Want **simple date filtering**? Use `/dl`
- Want **everything** or **complex control**? Use `/download` with "all"
- Need **specific message IDs**? Use `/download` with numbers

**The "all" shortcut works anywhere you used to type "1 0"!**
