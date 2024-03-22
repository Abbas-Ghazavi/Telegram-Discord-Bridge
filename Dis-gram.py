import asyncio
from queue import Queue
from telegram import Bot
from persiantools.jdatetime import JalaliDateTime
import pytz
import aiohttp
import re
from html import escape as html_escape

BOT_TOKEN = ''
TARGET_CHAT_ID = ''

message_queue = Queue()
last_messages = []

async def fetch_message(session, url, headers):
    async with session.get(url, headers=headers, params={"limit": 1}) as response:
        result = await response.json()
        await message_queue.put(result)

def get_reply_info(referenced_message):
    if referenced_message:
        referenced_author = referenced_message.get("author", {}).get("username", "Unknown")
        referenced_content = referenced_message.get("content", "")
        mentions = referenced_message.get("mentions", [])
        return {"author": referenced_author, "content": referenced_content, "mentions": mentions}
    return {}

async def incoming_message(bot: Bot, chat_id: str, author_name: str, content: str, send_time, send_date: str,
                           global_name: str, reply_info: dict, message: dict) -> None:
    is_bot = message.get("author", {}).get("bot", False)
    if "sticker_items" in message and message["sticker_items"]:
        return

    if is_bot:
        return
    
    display_name = author_name if global_name is None else global_name
    escaped_content = html_escape(content)

    mentions = message.get("mentions", [])
    if mentions:
        for mention in mentions:
            user_id = mention.get("id", "")
            username_preview = mention.get("username", "")
            mention_string = f"<@{user_id}>"
            content = content.replace(mention_string, f"@{username_preview}")

        message_text = f"<blockquote>{display_name} 💬 at <i>{send_time}</i></blockquote><b>{content.replace('(', r'\\(')}</b>\n"
    else:
        message_text = f"<blockquote>{display_name} 💬 at <i>{send_time}</i></blockquote><b>{escaped_content.replace('(', r'\\(')}</b>\n"

    if reply_info:
        referenced_author = reply_info.get("author", "Unknown")
        referenced_content = reply_info.get("content", "")


        reply_mentions = reply_info.get("mentions", [])
        for mention in reply_mentions:
            user_id = mention.get("id", "")
            username_preview = mention.get("username", "")
            mention_string = f"<@{user_id}>"
            referenced_content = referenced_content.replace(mention_string, f"@{username_preview}")

        reply_text = f"<blockquote>{display_name} ↪️ {referenced_author} at <i>{send_time}</i></blockquote>\n\n{referenced_author} : {html_escape(referenced_content).replace('(', r'\\(')}\n\n<blockquote><b>{display_name} : {escaped_content.replace('(', r'\\(')}</b></blockquote>"
        message_text = f"{reply_text}"

    media = message.get("attachments", [])
                               

    if media:
        for attachment in media:
            content_type = attachment.get("content_type", "")
            file_url = attachment.get("url", "")

            if content_type == "image/jpeg":
                await bot.send_photo(chat_id=chat_id, photo=file_url, caption=message_text, parse_mode='HTML')
            elif content_type == "video/mp4":
                await bot.send_video(chat_id=chat_id, video=file_url, caption=message_text, parse_mode='HTML')
            elif re.match(r'^application/', content_type):
                message_text = f"<blockquote>{display_name} 📤 at <i>{send_time}</i></blockquote><b>{content.replace('(', r'\\(')}\n<a href='{file_url}'>Download File</a></b>"
                await bot.send_message(chat_id=chat_id, text=message_text, parse_mode='HTML')
            else:
                await bot.send_message(chat_id=chat_id, text=message_text, parse_mode='HTML')
    else:
        await bot.send_message(chat_id=chat_id, text=message_text, parse_mode='HTML')

async def main(bot: Bot):
    urls = ["https://discord.com/api/v9/channels/(id text channel)"]

    headers = {"Authorization": "api user discord"}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector()) as session:
        last_message_id = None
        while True:
            try:
                tasks = [fetch_message(session, url, headers=headers) for url in urls]
                await asyncio.gather(*tasks, return_exceptions=True)

                while not message_queue.empty():
                    result = message_queue.get()
                    if isinstance(result, Exception):
                        print(f"An error occurred: {result}")
                        continue

                    message_list = result
                    for message in message_list:
                        if message not in last_messages:
                            last_messages.append(message)
                            if len(last_messages) > 10:
                                last_messages.pop(0)

                            message_id = message.get("id", "")
                            content = message.get("content", "")
                            author_name = message.get("author", {}).get("username", "Unknown")
                            global_name = message.get("author", {}).get("global_name", "Unknown")
                            timestamp = message.get("timestamp", "")

                            formatted_time_gregorian = JalaliDateTime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%f%z')
                            iran_timezone = pytz.timezone('Asia/Tehran')
                            send_time = formatted_time_gregorian.astimezone(iran_timezone).strftime('%H:%M:%S')
                            send_date = formatted_time_gregorian.astimezone(iran_timezone).strftime('%Y/%m/%d')

                            referenced_message = message.get("referenced_message", {})
                            reply_info = get_reply_info(referenced_message)

                            if message_id != last_message_id and "" in content:
                                await incoming_message(bot, TARGET_CHAT_ID, author_name, content, send_time, send_date,
                                                     global_name, reply_info, message.copy())
                                last_message_id = message_id

            except Exception as e:
                print(f"An error occurred: {e}")
                
if __name__ == "__main__":
    bot = Bot(token=BOT_TOKEN)
    asyncio.run(main(bot=bot))


