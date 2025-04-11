# main/__main__.py
import logging
from telethon import Button
from telethon import events
from telethon.tl.functions.messages import EditMessageRequest
from telethon.tl.custom.message import Message
import yt_dlp
import asyncio
import os
from telethon import errors, TelegramClient  # تم استيراد TelegramClient هنا (قد لا يكون مطلوبًا ولكن لا يضر)
import telethon  # تم استيراد الوحدة telethon هنا

from main.database import db
from main.client import bot
from main.config import Config
from main.utils import compress, get_video_info

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)

user_settings = {}
compression_tasks = {}  # قاموس لتتبع مهام الضغط وحالة الإلغاء


@bot.on(events.NewMessage(incoming=True, from_users=Config.WhiteList))
async def main_handler(event: events.NewMessage.Event):
    msg: Message = event.message
    chat_id = event.chat_id
    sender_id = event.sender_id

    if not event.is_private:
        return

    # Handle video uploads
    if event.media and hasattr(msg.media, "document") and 'video' in msg.media.document.mime_type:
        video_info = await get_video_info(msg.media.document, bot)
        codec = video_info.get('codec', 'N/A') if video_info else 'N/A'
        width = video_info.get('width', 'N/A') if video_info else 'N/A'
        height = video_info.get('height', 'N/A') if video_info else 'N/A'
        info_message = ""
        if not video_info:
            info_message = "⚠️ Could not retrieve complete video information.\n\n"

        settings_keyboard = [
            [Button.inline("⚙️ Compression Type", data=f"compression_type:{msg.id}"),
             Button.inline("📏 Resolution", data=f"resolution:{msg.id}")],
            [Button.inline("✨ Advanced Settings", data=f"advanced_settings:{msg.id}")],
            [Button.inline("▶️ Compress", data=f"start_compress:{msg.id}")]
        ]
        await event.reply(
            f"{info_message}**Video Information:**\nCodec: `{codec}`\nResolution: `{width}x{height}`\n\nSelect compression settings:",
            buttons=settings_keyboard,
            reply_to=msg.id
        )
        user_settings[sender_id] = {"video_message_id": msg.id, "settings": {}}
        return

    # Handle URLs
    if msg.text and msg.text.startswith(('http://', 'https://', 'www.')):
        await download_and_process_url(event, msg.text)
        return


async def download_and_process_url(event, url):
    chat_id = event.chat_id
    sender_id = event.sender_id
    try:
        ydl_opts = {
            'outtmpl': os.path.join(Config.InDir, '%(title)s-%(id)s.%(ext)s'),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            if 'entries' in info_dict:
                # Can be a playlist or a list of videos
                video = info_dict['entries'][0] if info_dict['entries'] else None
            else:
                video = info_dict

            if video:
                await event.reply(f"📥 Downloading: `{video.get('title', 'N/A')}`")
                ydl.download([url])
                file_path = ydl.prepare_filename(video)

                # Simulate a message object for the downloaded file
                class DummyMessage:
                    def __init__(self, chat_id, file_path):
                        self.chat_id = chat_id
                        self.file_path = file_path
                        self.id = None  # No message ID for downloaded file

                dummy_msg = DummyMessage(chat_id, file_path)

                video_info = await get_video_info(file_path, bot, is_file_path=True)
                codec = video_info.get('codec', 'N/A') if video_info else 'N/A'
                width = video_info.get('width', 'N/A') if video_info else 'N/A'
                height = video_info.get('height', 'N/A') if video_info else 'N/A'
                info_message = ""
                if not video_info:
                    info_message = "⚠️ Could not retrieve complete video information.\n\n"

                settings_keyboard = [
                    [Button.inline("⚙️ Compression Type", data=f"compression_type:url:{url}"),
                     Button.inline("📏 Resolution", data=f"resolution:url:{url}")],
                    [Button.inline("✨ Advanced Settings", data=f"advanced_settings:url:{url}")],
                    [Button.inline("▶️ Compress", data=f"start_compress:url:{url}")]
                ]
                await event.reply(
                    f"{info_message}**Downloaded Video Information:**\nCodec: `{codec}`\nResolution: `{width}x{height}`\n\nSelect compression settings:",
                    buttons=settings_keyboard
                )
                user_settings[sender_id] = {"url": url, "file_path": file_path, "settings": {}}
            else:
                await event.reply("⚠️ Could not find video information for the provided URL.")

    except yt_dlp.DownloadError as e:
        await event.reply(f"⚠️ Error downloading video from URL: `{e}`")
    except Exception as e:
        print(f"Error processing URL: {e}")
        await event.reply("⚠️ An unexpected error occurred while processing the URL.")


@bot.on(events.CallbackQuery(pattern=r"compression_type:(?:url:)?(.+)"))
async def compression_type_callback(event):
    sender_id = event.sender_id
    message_identifier = event.pattern_match.group(1)
    settings_keyboard = [
        [Button.inline("Ultra Fast", data=f"set_speed:ultrafast:{message_identifier}"),
         Button.inline("Very Fast", data=f"set_speed:veryfast:{message_identifier}")],
        [Button.inline("Fast", data=f"set_speed:fast:{message_identifier}"),
         Button.inline("Medium", data=f"set_speed:medium:{message_identifier}")],
        [Button.inline("Slow", data=f"set_speed:slow:{message_identifier}")],
        [Button.inline("Back", data=f"back_to_main:{message_identifier}")]
    ]
    try:
        await event.edit("Select Compression Speed:", buttons=settings_keyboard)
    except telethon.errors.rpcerrorlist.MessageNotModifiedError:
        pass


@bot.on(events.CallbackQuery(pattern=r"set_speed:(.+):(.+)"))
async def set_speed_callback(event):
    sender_id = event.sender_id
    speed = event.pattern_match.group(1)
    message_identifier = event.pattern_match.group(2)
    if sender_id in user_settings:
        user_settings[sender_id]["settings"]["speed"] = speed
        await event.answer(f"✅ Speed set to {speed}")
    else:
        await event.answer("⚠️ No video selected. Send a video first.")


@bot.on(events.CallbackQuery(pattern=r"resolution:(?:url:)?(.+)"))
async def resolution_callback(event):
    sender_id = event.sender_id
    message_identifier = event.pattern_match.group(1)
    settings_keyboard = [
        [Button.inline("Original", data=f"set_resolution:original:{message_identifier}"),
         Button.inline("240p", data=f"set_resolution:240p:{message_identifier}")],
        [Button.inline("360p", data=f"set_resolution:360p:{message_identifier}"),
         Button.inline("480p", data=f"set_resolution:480p:{message_identifier}")],
        [Button.inline("720p", data=f"set_resolution:720p:{message_identifier}"),
         Button.inline("1080p", data=f"set_resolution:1080p:{message_identifier}")],
        [Button.inline("Custom", data=f"custom_resolution:{message_identifier}")],
        [Button.inline("Back", data=f"back_to_main:{message_identifier}")]
    ]
    await event.edit("Select Resolution:", buttons=settings_keyboard)


@bot.on(events.CallbackQuery(pattern=r"set_resolution:(.+):(.+)"))
async def set_resolution_callback(event):
    sender_id = event.sender_id
    resolution = event.pattern_match.group(1)
    message_identifier = event.pattern_match.group(2)
    if sender_id in user_settings:
        user_settings[sender_id]["settings"]["resolution"] = resolution
        if resolution == 'original':
            user_settings[sender_id]["settings"].pop('width', None)
            user_settings[sender_id]["settings"].pop('height', None)
            await event.answer("✅ Resolution set to Original")
        else:
            user_settings[sender_id]["settings"].pop('width', None)
            user_settings[sender_id]["settings"].pop('height', None)
            await event.answer(f"✅ Resolution set to {resolution}")
    else:
        await event.answer("⚠️ No video selected. Send a video first.")


@bot.on(events.CallbackQuery(pattern=r"custom_resolution:(.+)"))
async def custom_resolution_callback(event):
    sender_id = event.sender_id
    message_identifier = event.pattern_match.group(1)
    await bot.send_message(event.chat_id, f"Please send the custom resolution in the format `widthxheight` (e.g., `640x480`) as a reply to this message.", reply_to=event.message.id)
    await bot.add_event_handler(custom_resolution_handler, events.NewMessage(from_users=sender_id, pattern=r"^\d+x\d+$", func=lambda e: e.is_reply and e.reply_to_msg_id == event.message.id))


async def custom_resolution_handler(event):
    sender_id = event.sender_id
    resolution_str = event.text
    width, height = map(int, resolution_str.split('x'))
    if sender_id in user_settings:
        user_settings[sender_id]["settings"]["width"] = width
        user_settings[sender_id]["settings"]["height"] = height
        await event.reply(f"✅ Custom resolution set to {width}x{height}")
    else:
        await event.reply("⚠️ No video selected. Send a video first.")
    bot.remove_event_handler(custom_resolution_handler)


@bot.on(events.CallbackQuery(pattern=r"advanced_settings:(?:url:)?(.+)"))
async def advanced_settings_callback(event):
    sender_id = event.sender_id
    message_identifier = event.pattern_match.group(1)
    settings_keyboard = [
        [Button.inline("FPS", data=f"set_fps_menu:{message_identifier}"),
         Button.inline("CRF", data=f"set_crf_menu:{message_identifier}")],
        [Button.inline("Back", data=f"back_to_main:{message_identifier}")]
    ]
    await event.edit("Select Advanced Settings:", buttons=settings_keyboard)


@bot.on(events.CallbackQuery(pattern=r"set_fps_menu:(.+)"))
async def set_fps_menu_callback(event):
    sender_id = event.sender_id
    message_identifier = event.pattern_match.group(1)
    settings_keyboard = [
        [Button.inline("30", data=f"set_fps:30:{message_identifier}"),
         Button.inline("45", data=f"set_fps:45:{message_identifier}")],
        [Button.inline("60", data=f"set_fps:60:{message_identifier}"),
         Button.inline("Original", data=f"set_fps:original:{message_identifier}")],
        [Button.inline("Back", data=f"back_to_advanced:{message_identifier}")]
    ]
    await event.edit("Select FPS:", buttons=settings_keyboard)


@bot.on(events.CallbackQuery(pattern=r"set_fps:(.+):(.+)"))
async def set_fps_callback(event):
    sender_id = event.sender_id
    fps_value = event.pattern_match.group(1)
    message_identifier = event.pattern_match.group(2)
    if sender_id in user_settings:
        user_settings[sender_id]["settings"]["fps"] = int(fps_value) if fps_value != 'original' else None
        await event.answer(f"✅ FPS set to {fps_value}")
    else:
        await event.answer("⚠️ No video selected. Send a video first.")


@bot.on(events.CallbackQuery(pattern=r"set_crf_menu:(.+)"))
async def set_crf_menu_callback(event):
    sender_id = event.sender_id
    message_identifier = event.pattern_match.group(1)
    settings_keyboard = [
        [Button.inline(str(i), data=f"set_crf:{i}:{message_identifier}") for i in range(20, 26)],
        [Button.inline(str(i), data=f"set_crf:{i}:{message_identifier}") for i in range(26, 31)],
        [Button.inline("Back", data=f"back_to_advanced:{message_identifier}")]
    ]
    await event.edit("Select CRF (Compression Ratio):", buttons=settings_keyboard)


@bot.on(events.CallbackQuery(pattern=r"set_crf:(.+):(.+)"))
async def set_crf_callback(event):
    sender_id = event.sender_id
    crf_value = event.pattern_match.group(1)
    message_identifier = event.pattern_match.group(2)
    if sender_id in user_settings:
        user_settings[sender_id]["settings"]["crf"] = int(crf_value)
        await event.answer(f"✅ CRF set to {crf_value}")
    else:
        await event.answer("⚠️ No video selected. Send a video first.")


@bot.on(events.CallbackQuery(pattern=r"back_to_main:(.+)"))
async def back_to_main_callback(event):
    sender_id = event.sender_id
    message_identifier = event.pattern_match.group(1)
    if sender_id in user_settings:
        msg_id = user_settings[sender_id].get("video_message_id")
        settings_keyboard = [
            [Button.inline("⚙️ Compression Type", data=f"compression_type:{msg_id}"),
             Button.inline("📏 Resolution", data=f"resolution:{msg_id}")],
            [Button.inline("✨ Advanced Settings", data=f"advanced_settings:{msg_id}")],
            [Button.inline("▶️ Compress", data=f"start_compress:{msg_id}")]
        ]
        try:
            await event.edit("Select compression settings:", buttons=settings_keyboard)
        except telethon.errors.rpcerrorlist.MessageNotModifiedError:
            pass
    else:
        await event.answer("⚠️ No video selected. Send a video first.")


@bot.on(events.CallbackQuery(pattern=r"back_to_advanced:(.+)"))
async def back_to_advanced_callback(event):
    sender_id = event.sender_id
    message_identifier = event.pattern_match.group(1)
    settings_keyboard = [
        [Button.inline("FPS", data=f"set_fps_menu:{message_identifier}"),
         Button.inline("CRF", data=f"set_crf_menu:{message_identifier}")],
        [Button.inline("Back", data=f"back_to_main:{message_identifier}")]
    ]
    try:
        await event.edit("Select Advanced Settings:", buttons=settings_keyboard)
    except telethon.errors.rpcerrorlist.MessageNotModifiedError:
        pass


@bot.on(events.CallbackQuery(pattern=r"start_compress:(url:)?(.+)"))
async def start_compress_callback(event):
    sender_id = event.sender_id
    message_identifier = event.pattern_match.group(2)
    is_url = event.pattern_match.group(1) == "url:"

    if sender_id in user_settings:
        settings = user_settings[sender_id]["settings"]
        initial_message = await event.reply("🔄 **Compression started...**")
        cancel_button = [Button.inline("❌ Cancel Compression", data=f"cancel_compress:{initial_message.id}")]
        try:
            await bot.edit_message(event.chat_id, initial_message.id, "🔄 **Compression started...**", buttons=cancel_button)
        except errors.MessageNotModifiedError:
            pass

        task_id = initial_message.id  # استخدام معرف الرسالة كمعرف للمهمة
        compression_tasks[task_id] = {"status": "running", "sender_id": sender_id, "file_paths": []} # تتبع المهمة

        if is_url:
            file_path = user_settings[sender_id].get("file_path")
            if file_path:
                try:
                    db.tasks += 1
                    compression_tasks[task_id]["file_paths"].append(file_path) # تتبع مسار الملف
                    await compress(event, file_path=file_path, task_id=task_id, **settings) # تمرير معرف المهمة
                except Exception as e:
                    print(e)
                    await bot.edit_message(event.chat_id, initial_message.id, f"⚠️ Compression failed: {e}")
                    compression_tasks[task_id]["status"] = "failed"
                finally:
                    db.tasks -= 1
                    if task_id in compression_tasks and compression_tasks[task_id]["status"] != "cancelled" and os.path.exists(file_path):
                        os.remove(file_path)
                    if task_id in compression_tasks:
                        del compression_tasks[task_id]
            else:
                await event.answer("⚠️ Downloaded file path not found.")
                if task_id in compression_tasks:
                    del compression_tasks[task_id]
        else:
            try:
                original_messages = await bot.get_messages(event.chat_id, ids=user_settings[sender_id]["video_message_id"])
                if original_messages and len(original_messages) > 0:
                    original_message = original_messages[0]
                    if original_message and original_message.media:
                        if db.tasks >= Config.Max_Tasks:
                            await bot.edit_message(event.chat_id, initial_message.id, f"💢 **Tʜᴇʀᴇ Aʀᴇ** {Config.Max_Tasks} **Tᴀѕᴋѕ Wᴏʀᴋɪɴɢ Nᴏᴡ**")
                            if task_id in compression_tasks:
                                del compression_tasks[task_id]
                            return
                        try:
                            db.tasks += 1
                            await compress(event, video_document=original_message.media.document, task_id=task_id, **settings) # تمرير معرف المهمة
                        except Exception as e:
                            print(e)
                            await bot.edit_message(event.chat_id, initial_message.id, f"⚠️ Compression failed: {e}")
                            compression_tasks[task_id]["status"] = "failed"
                        finally:
                            db.tasks -= 1
                            if task_id in compression_tasks and compression_tasks[task_id]["status"] == "running":
                                await bot.edit_message(event.chat_id, initial_message.id, "✅ **Compression finished.**")
                            if task_id in compression_tasks:
                                del compression_tasks[task_id]
                    else:
                        await event.answer("⚠️ Original video message does not contain media.")
                        if task_id in compression_tasks:
                            del compression_tasks[task_id]
                else:
                    await event.answer("⚠️ Original video message not found.")
                    if task_id in compression_tasks:
                        del compression_tasks[task_id]
            except errors.MessageIdInvalidError:
                await event.answer("⚠️ Original video message not found (ID invalid).")
                if task_id in compression_tasks:
                    del compression_tasks[task_id]
            except Exception as e:
                print(f"Error in start_compress_callback: {e}")
                await event.answer("⚠️ An error occurred while trying to start compression.")
                if task_id in compression_tasks:
                    del compression_tasks[task_id]
        if sender_id in user_settings:
            del user_settings[sender_id]
    else:
        await event.answer("⚠️ No video selected. Send a video first.")


@bot.on(events.CallbackQuery(pattern=r"cancel_compress:(\d+)"))
async def cancel_compress_callback(event):
    task_id = int(event.pattern_match.group(1))
    sender_id = event.sender_id
    if task_id in compression_tasks and compression_tasks[task_id]["sender_id"] == sender_id:
        compression_tasks[task_id]["status"] = "cancelled"
        file_paths_to_delete = compression_tasks[task_id].get("file_paths", [])
        for file_path in file_paths_to_delete:
            if os.path.exists(file_path):
                os.remove(file_path)
        try:
            await bot.edit_message(event.chat_id, task_id, "❌ **Compression cancelled by user.**")
        except errors.MessageNotModifiedError:
            pass
        del compression_tasks[task_id]
        await event.answer("Compression cancelled.")
    else:
        await event.answer("⚠️ This compression task cannot be cancelled.")


@bot.on(events.NewMessage(incoming=True, pattern="/as_video", from_users=Config.WhiteList))
async def as_video(event):
    await db.set_upload_mode(doc=False)
    await bot.send_message(event.chat_id, "✅ **I Wɪʟʟ Uᴘʟᴏᴀᴅ Tʜᴇ Fɪʟᴇѕ Aѕ Vɪᴅᴇᴏѕ**")


@bot.on(events.NewMessage(incoming=True, pattern="/as_document", from_users=Config.WhiteList))
async def as_document(event):
    await db.set_upload_mode(doc=True)
    await bot.send_message(event.chat_id, "✅ **I Wɪʟʟ Uᴘʟᴏᴀᴅ Tʜᴇ Fɪʟᴇѕ Aѕ Dᴏᴄᴜᴍᴇɴᴛѕ**")


@bot.on(events.NewMessage(incoming=True, pattern="/speed", from_users=Config.WhiteList))
async def set_speed_command(event):
    msg: Message = event.message
    parts = msg.text.split()
    if len(parts) != 2:
        await bot.send_message(event.chat_id, "🚀**Sᴇʟᴇᴄᴛɪᴏɴ Oғ Cᴏᴍᴘʀᴇѕѕɪᴏɴ Sᴘᴇᴇᴅ**\n\n "
                                              "`/speed veryfast` \n\n`/speed fast`\n\n`/speed ultrafast`")
    else:
        await db.set_speed(parts[1])
        await bot.send_message(event.chat_id, "✅ **Dᴏɴᴇ**")


@bot.on(events.NewMessage(incoming=True, pattern="/crf", from_users=Config.WhiteList))
async def set_crf_command(event):
    msg: Message = event.message
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isnumeric():
        await bot.send_message(event.chat_id, "⚡️ **Sᴇʟᴇᴄᴛɪᴏɴ Oғ Cᴏᴍᴘʀᴇѕѕɪᴏɴ Rᴀᴛɪᴏ**\n\n `/crf 28`    ↩ ↪   `/crf 27`")
    else:
        await db.set_crf(int(parts[1]))
        await bot.send_message(event.chat_id, "✅ **Dᴏɴᴇ**")


@bot.on(events.NewMessage(incoming=True, pattern="/fps", from_users=Config.WhiteList))
async def set_fps_command(event):
    msg: Message = event.message
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isnumeric():
        await bot.send_message(event.chat_id, "💢 **Iɴᴠᴀʟɪᴅ SʏɴᴛᴀХ**\n**Eхᴀᴍᴘʟᴇ**: `/fps 24`")
    else:
        await db.set_fps(int(parts[1]))
        await bot.send_message(event.chat_id, "✅ **Dᴏɴᴇ**")


@bot.on(events.NewMessage(incoming=True, func=lambda e: e.photo, from_users=Config.WhiteList))
async def set_thumb(event):
    await bot.download_media(event.message, Config.Thumb)
    await db.set_thumb(original=False)
    await event.reply("✅ **Tʜᴜᴍʙɴᴀɪʟ CʜᴀɴɢᴇD**")


@bot.on(events.NewMessage(incoming=True, pattern="/original_thumb", from_users=Config.WhiteList))
async def original_thumb(event):
    await db.set_thumb(original=True)
    await event.reply("✅ **ɪ Wɪʟʟ Uѕᴇ Oʀɪɢɪɴᴀʟ Tʜᴜᴍʙɴᴀɪʟ**")


@bot.on(events.NewMessage(incoming=True, pattern="/original_fps", from_users=Config.WhiteList))
async def original_fps(event):
    await db.set_fps(None)
    await event.reply("✅ **I Wɪʟʟ Uѕᴇ Oʀɪɢɪɴᴀʟ FPS**")


@bot.on(events.NewMessage(incoming=True, pattern="/commands", from_users=Config.WhiteList))
async def commands(event):
    await event.reply("🤖 **Vɪᴅᴇᴏ Cᴏᴍᴘʀᴇѕѕɪᴏɴ Sᴇᴛᴛɪɴɢѕ**:\n\n/speed  **Cᴏᴍᴘʀᴇѕѕɪᴏɴ Sᴘᴇᴇᴅ**\n\n"
                      "/crf   **Cᴏᴍᴘʀᴇѕѕɪᴏɴ Rᴀᴛɪᴏ**\n\n/fps  **Fʀᴀᴍᴇѕ Pᴇʀ Sᴇᴄᴏɴᴅ**\n/original_fps   **Dᴇғᴀᴜʟᴛ FPS**\n\n"
                      "/as_video   **Uᴘʟᴏᴀᴅ Aѕ Vɪᴅᴇᴏ**\n/as_document  **Uᴘʟᴏᴀᴅ Aѕ Fɪʟᴇ**\n\n"
                      "/original_thumb **Dᴇғᴀᴜʟᴛ Tʜᴜᴍʙɴᴀɪʟ**\n\n🖼 **Sᴇɴᴅ Aɴʏ Pɪᴄᴛᴜʀᴇ Tᴏ Sᴇᴛ Iᴛ Aѕ Tʜᴜᴍʙɴᴀɪʟ**")


@bot.on(events.CallbackQuery())
async def callback_handler(event):
    if event.sender_id not in Config.WhiteList:
        await event.answer("⛔️ Ꮪᴏʀʀʏ, Ꭲʜɪѕ Ᏼᴏᴛ Fᴏʀ Ꮲᴇʀѕᴏɴᴀʟ Uѕᴇ !! ⛔️")
        return
    # Existing callback handlers for settings menu will remain as they are for now.
    # The new logic is implemented above.
    pass


@bot.on(events.NewMessage(incoming=True, pattern="/start"))
async def start_handler(event):
    if event.sender_id not in Config.WhiteList:
        await event.reply("Ꮪᴏʀʀʏ, Ꭲʜɪѕ Ᏼᴏᴛ Fᴏʀ Ꮲᴇʀѕᴏɴᴀʟ Uѕᴇ\n\n**Yᴏᴜ Aʀᴇ Nᴏᴛ Aᴜᴛʜᴏʀɪᴢᴇᴅ Tᴏ Uѕᴇ Tʜɪѕ Ᏼᴏᴛ!!**⛔️")
        return
    settings = Button.inline("⚙ Sᴇᴛᴛɪɴɢs", data="settings")
    developer = Button.url("Ꭰᴇᴠᴇʟᴏᴘᴇʀ 💫", url="https://t.me/A7_SYR")
    text = "Sᴇɴᴅ Mᴇ Aɴʏ Vɪᴅᴇᴏ Tᴏ Cᴏᴍᴘʀᴇѕѕ\n\nᏟʟɪᴄᴋ Ᏼᴜᴛᴛᴏɴ ⚙ Sᴇᴛᴛɪɴɢѕ"
    await event.reply(text, buttons=[[settings, developer]])


@bot.on(events.CallbackQuery(data="settings"))
async def settingscallback(event):
    compress_button = Button.inline("⚙️ Compression Settings", data="new_settings")
    back = Button.inline("Back", data="back_start")
    text = "**⚙️ Bot Settings**"
    await event.edit(text, buttons=[[compress_button], [back]])


@bot.on(events.CallbackQuery(data="new_settings"))
async def new_settings_callback(event):
    await event.answer("Send me a video to configure compression settings.")


@bot.on(events.CallbackQuery(data="back_start"))
async def back_start_callback(event):
    settings = Button.inline("⚙ Sᴇᴛᴛɪɴgs", data="settings")
    developer = Button.url("Ꭰᴇᴠᴇʟᴏᴘᴇʀ 💫", url="https://t.me/A7_SYR")
    text = "Sᴇɴᴅ Mᴇ Aɴʏ Vɪᴅᴇᴏ Tᴏ Cᴏᴍᴘʀᴇѕѕ\n\nᏟʟɪᴄᴋ Ᏼᴜᴛᴛᴏɴ **⚙ Sᴇᴛᴛɪɴgs**\n\nᏴᴇғᴏʀᴇ Ꮪᴇɴᴅɪɴɢ Ꭲʜᴇ Ꮩɪᴅᴇᴏ ғᴏʀ Ꮯᴏᴍᴘʀᴇѕѕɪᴏɴ\n👇"
    await event.edit(text, buttons=[[settings, developer]])


bot.loop.run_until_complete(db.init())
print("Bot-Started")
bot.run_until_disconnected()
