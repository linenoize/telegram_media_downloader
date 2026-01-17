

import pyrogram
from pyrogram import filters
from pyrogram.handlers import MessageHandler

async def search_mega_links(client: pyrogram.Client, message: pyrogram.types.Message, _bot_instance):
    """
    Searches for messages containing mega.nz or mega.co.nz links in a specified chat.
    """
    if len(message.text.split()) != 2:
        await message.reply_text("Usage: /search_mega [chat_id]")
        return

    chat_id = message.text.split()[1]
    links = []
    
    try:
        async for msg in _bot_instance.client.search_messages(chat_id, query="mega."):
            if msg.text:
                if "mega.nz" in msg.text or "mega.co.nz" in msg.text:
                    links.append(msg.link)
    except Exception as e:
        await message.reply_text(f"An error occurred: {e}")
        return

    if links:
        await message.reply_text("\n".join(links))
    else:
        await message.reply_text("No mega links found.")

def add_search_handler(_bot_instance):
    _bot_instance.bot.add_handler(
        MessageHandler(
            lambda client, message: search_mega_links(client, message, _bot_instance),
            filters=filters.command(["search_mega"]) 
            & filters.user(_bot_instance.allowed_user_ids),
        )
    )

