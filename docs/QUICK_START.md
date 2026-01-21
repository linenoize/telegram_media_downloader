# Quick Start Guide: Autostart and Cleanup Features

## What's New?

Your Telegram Media Downloader now includes two powerful features:

1. **Autostart** - Automatically catches up on downloads when the app starts
2. **Cleanup** - Keeps your chats clean by removing already-downloaded messages

## Autostart (Already Working!)

Good news! The autostart feature already exists and works automatically:

- When you start the app, it downloads from **all** configured chats
- Any media added while the app was offline will be downloaded automatically
- No configuration needed - it just works!

## Cleanup Feature (New!)

### Quick Setup

1. **Add to your `config.yaml`:**

```yaml
cleanup:
  enabled: true
  idle_hours: 3
  delete_skipped_messages: true
  delete_bot_status: false
```

2. **Restart the application**

3. **That's it!** The cleanup will run automatically after 3 hours of no downloads

### What Does It Do?

The cleanup feature:
- ✅ Waits for 3 hours (configurable) with no downloads
- ✅ Deletes messages that were skipped because already downloaded
- ✅ Logs other skipped items to `logs/skipped_items.log` for your review
- ✅ Runs in the background without interfering with downloads

### Configuration Options

| Setting | What It Does | Default |
|---------|--------------|---------|
| `enabled` | Turn cleanup on/off | `true` |
| `idle_hours` | Hours to wait before cleanup | `3` |
| `delete_skipped_messages` | Delete already-downloaded messages | `true` |
| `delete_bot_status` | Delete bot status messages | `false` |

### Common Scenarios

**Scenario 1: I want faster cleanup (after 1 hour)**
```yaml
cleanup:
  enabled: true
  idle_hours: 1
  delete_skipped_messages: true
  delete_bot_status: false
```

**Scenario 2: I'm using the bot and want to clean bot messages too**
```yaml
cleanup:
  enabled: true
  idle_hours: 3
  delete_skipped_messages: true
  delete_bot_status: true  # ← Changed to true
```

**Scenario 3: I don't want automatic cleanup**
```yaml
cleanup:
  enabled: false  # ← Just set to false
```

## How It Works

```
1. App starts → Downloads everything from configured chats (autostart)
                                    ↓
2. Downloads complete → Idle timer starts counting
                                    ↓
3. 3 hours pass (no downloads) → Cleanup runs automatically
                                    ↓
4. Already-downloaded messages → Deleted from chat
                                    ↓
5. Other skipped messages → Logged to file for review
```

## Checking the Logs

### Activity Logs
Normal logs show cleanup activity:
```
INFO: Cleanup manager enabled - will run after 3 hours of inactivity
INFO: No downloads for 3.0 hours, starting cleanup...
INFO: Deleted 45 already-downloaded messages from chat testline_ml_bot
INFO: Cleanup completed - Deleted: 45, Logged skipped items: 2, Duration: 3.21s
```

### Skipped Items Log
Check `logs/skipped_items.log` for messages skipped for other reasons:
```
[2026-01-13T10:30:45] Chat: testline_ml_bot, Message ID: 12345, Reason: Skipped (not already downloaded)
[2026-01-13T10:31:12] Chat: UnsupportedUser64Bot, Message ID: 67890, Reason: Skipped (not already downloaded)
```

## Important Notes

⚠️ **Warning**: Deleted messages cannot be recovered!

✅ **Good to Know**:
- Cleanup only deletes messages that were skipped because already downloaded
- Messages skipped for other reasons (filters, format, etc.) are NOT deleted
- Those other skipped messages are logged for your review
- The idle timer resets every time a successful download happens

## Troubleshooting

### Cleanup isn't running

**Check**:
1. Is `enabled: true` in config?
2. Has 3 hours (or your configured time) passed with NO downloads?
3. Are there any error messages in the logs?

### Messages aren't being deleted

**Check**:
1. Does your bot/user have permission to delete messages?
2. Is `delete_skipped_messages: true`?
3. Check logs for "FloodWait" errors (too many API requests)

### How do I know it's working?

**Look for**:
1. At startup: "Cleanup manager enabled - will run after X hours"
2. After idle time: "No downloads for X hours, starting cleanup..."
3. During cleanup: "Deleted X already-downloaded messages from chat..."
4. After cleanup: "Cleanup completed - Deleted: X, ..."

## Need More Help?

- **Full Documentation**: See `docs/CLEANUP.md`
- **Implementation Details**: See `docs/IMPLEMENTATION_SUMMARY.md`
- **Issues**: Check the logs at `log/tdl.log`

## Summary

You now have:
- ✅ **Autostart**: Catches up on downloads when app starts (already working)
- ✅ **Cleanup**: Keeps chats clean by removing already-downloaded messages
- ✅ **Smart Filtering**: Only deletes what's already downloaded
- ✅ **Logging**: Tracks everything else for review

Just add the config, restart, and you're good to go!
