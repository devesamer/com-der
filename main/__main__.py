# main/__main__.py

import logging
from telethon import Button
from telethon import events
from telethon.tl.functions.messages import EditMessageRequest
from telethon.tl.custom.message import Message

from main.database import db
from main.client import bot
from main.config import Config
from main.utils import compress

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)

user_settings = {}  # Dictionary to store user-specific settings


async def send_settings_keyboard(user_id, video_message: Message):
    buttons = [
        [Button.inline("⚙️ Compression Type", data=f"compression_type:{video_message.id}"),
         Button.inline("📐 Resolution", data=f"resolution:{video_message.id}")],
        [Button.inline("🎬 FPS", data=f"fps_select:{video_message.id}"),
         Button.inline("📊 CRF", data=f"crf_select:{video_message.id}")],
        [Button.inline("🚀 Start Compress", data=f"start_compress:{video_message.id}")]
    ]
    text = "Please select the desired compression settings:"
    try:
        await bot.send_message(user_id, text, buttons=buttons, reply_to=video_message.id)
    except Exception as e:
        logging.error(f"Error sending settings keyboard: {e}")
        await bot.send_message(user_id, "An error occurred while displaying settings.")


@bot.on(events.NewMessage(incoming=True, from_users=Config.WhiteList))
async def video_handler(event: events.NewMessage.Event):
    msg: Message = event.message
    if not event.is_private or not event.media or not hasattr(msg.media, "document"):
        return
    if 'video' not in msg.media.document.mime_type:
        return

    user_id = event.sender_id
    user_settings[user_id] = {
        "video_message_id": msg.id,
        "speed": None,
        "resolution": None,
        "fps": None,
        "crf": None,
        "upload_as_doc": db.doc  # Inherit current upload mode
    }

    await send_settings_keyboard(user_id, msg)


async def update_settings_message(event: events.CallbackQuery.Event, text, buttons):
    try:
        await event.edit(text, buttons=buttons)
    except Exception as e:
        logging.error(f"Error updating settings message: {e}")
        await event.answer("An error occurred while updating settings.")


@bot.on(events.CallbackQuery(pattern=r"compression_type:(\d+)"))
async def compression_type_callback(event):
    user_id = event.sender_id
    video_message_id = int(event.pattern_match.group(1))

    buttons = [
        [Button.inline("High Quality (Slow)", data=f"set_speed:slow:{video_message_id}"),
         Button.inline("Medium Quality (Medium)", data=f"set_speed:medium:{video_message_id}")],
        [Button.inline("Low Quality (Fast)", data=f"set_speed:ultrafast:{video_message_id}")],
        [Button.inline("Back to Settings", data=f"back_to_settings:{video_message_id}")]
    ]
    text = "Select the desired compression quality/speed:"
    await bot.send_message(user_id, text, buttons=buttons, reply_to=video_message_id)
    await event.answer()

@bot.on(events.CallbackQuery(pattern=r"set_speed:(.+):(\d+)"))
async def set_speed_callback(event):
    user_id = event.sender_id
    speed = event.pattern_match.group(1)
    video_message_id = int(event.pattern_match.group(2))

    if user_id in user_settings and user_settings[user_id]["video_message_id"] == video_message_id:
        user_settings[user_id]["speed"] = speed
        await event.answer(f"Compression speed set to: {speed.replace('fast', ' Fast').title()}".encode())
        await send_settings_keyboard(user_id, await bot.get_messages(event.chat_id, ids=video_message_id))
    else:
        await event.answer("Invalid operation.")


@bot.on(events.CallbackQuery(pattern=r"resolution:(\d+)"))
async def resolution_callback(event):
    user_id = event.sender_id
    video_message_id = int(event.pattern_match.group(1))

    buttons = [
        [Button.inline("240p", data=f"set_resolution:240p:{video_message_id}"),
         Button.inline("360p", data=f"set_resolution:360p:{video_message_id}")],
        [Button.inline("480p", data=f"set_resolution:480p:{video_message_id}"),
         Button.inline("720p", data=f"set_resolution:720p:{video_message_id}")],
        [Button.inline("1080p", data=f"set_resolution:1080p:{video_message_id}")],
        [Button.inline("Back to Settings", data=f"back_to_settings:{video_message_id}")]
    ]
    text = "Select the desired resolution:"
    await bot.send_message(user_id, text, buttons=buttons, reply_to=video_message_id)
    await event.answer()

@bot.on(events.CallbackQuery(pattern=r"set_resolution:(.+):(\d+)"))
async def set_resolution_callback(event):
    user_id = event.sender_id
    resolution = event.pattern_match.group(1)
    video_message_id = int(event.pattern_match.group(2))

    if user_id in user_settings and user_settings[user_id]["video_message_id"] == video_message_id:
        user_settings[user_id]["resolution"] = resolution
        await event.answer(f"Resolution set to: {resolution}".encode())
        await send_settings_keyboard(user_id, await bot.get_messages(event.chat_id, ids=video_message_id))
    else:
        await event.answer("Invalid operation.")


@bot.on(events.CallbackQuery(pattern=r"fps_select:(\d+)"))
async def fps_select_callback(event):
    user_id = event.sender_id
    video_message_id = int(event.pattern_match.group(1))

    buttons = [
        [Button.inline("Original FPS", data=f"set_fps:original:{video_message_id}"),
         Button.inline("30", data=f"set_fps:30:{video_message_id}")],
        [Button.inline("25", data=f"set_fps:25:{video_message_id}"),
         Button.inline("24", data=f"set_fps:24:{video_message_id}")],
        [Button.inline("Back to Settings", data=f"back_to_settings:{video_message_id}")]
    ]
    text = "Select the desired frames per second (FPS):"
    await bot.send_message(user_id, text, buttons=buttons, reply_to=video_message_id)
    await event.answer()

@bot.on(events.CallbackQuery(pattern=r"set_fps:(.+):(\d+)"))
async def set_fps_callback(event):
    user_id = event.sender_id
    fps_value = event.pattern_match.group(1)
    video_message_id = int(event.pattern_match.group(2))

    if user_id in user_settings and user_settings[user_id]["video_message_id"] == video_message_id:
        user_settings[user_id]["fps"] = fps_value if fps_value != "original" else None
        await event.answer(f"FPS set to: {fps_value}".encode())
        await send_settings_keyboard(user_id, await bot.get_messages(event.chat_id, ids=video_message_id))
    else:
        await event.answer("Invalid operation.")


@bot.on(events.CallbackQuery(pattern=r"crf_select:(\d+)"))
async def crf_select_callback(event):
    user_id = event.sender_id
    video_message_id = int(event.pattern_match.group(1))

    buttons = [
        [Button.inline("20 (Highest Quality)", data=f"set_crf:20:{video_message_id}"),
         Button.inline("23", data=f"set_crf:23:{video_message_id}")],
        [Button.inline("26 (Recommended)", data=f"set_crf:26:{video_message_id}"),
         Button.inline("28", data=f"set_crf:28:{video_message_id}")],
        [Button.inline("30 (Lowest Quality)", data=f"set_crf:30:{video_message_id}")],
        [Button.inline("Back to Settings", data=f"back_to_settings:{video_message_id}")]
    ]
    text = "Select the Constant Rate Factor (CRF) value:\nLower values mean higher quality and larger file size."
    await bot.send_message(user_id, text, buttons=buttons, reply_to=video_message_id)
    await event.answer()

@bot.on(events.CallbackQuery(pattern=r"set_crf:(\d+):(\d+)"))
async def set_crf_callback(event):
    user_id = event.sender_id
    crf_value = int(event.pattern_match.group(1))
    video_message_id = int(event.pattern_match.group(2))

    if user_id in user_settings and user_settings[user_id]["video_message_id"] == video_message_id:
        user_settings[user_id]["crf"] = crf_value
        await event.answer(f"CRF set to: {crf_value}".encode())
        await send_settings_keyboard(user_id, await bot.get_messages(event.chat_id, ids=video_message_id))
    else:
        await event.answer("Invalid operation.")


@bot.on(events.CallbackQuery(pattern=r"back_to_settings:(\d+)"))
async def back_to_settings_callback(event):
    user_id = event.sender_id
    video_message_id = int(event.pattern_match.group(1))
    original_message = await bot.get_messages(event.chat_id, ids=video_message_id)
    if original_message:
        await send_settings_keyboard(user_id, original_message)
    await event.answer()


@bot.on(events.CallbackQuery(pattern=r"start_compress:(\d+)"))
async def start_compress_callback(event):
    user_id = event.sender_id
    video_message_id = int(event.pattern_match.group(1))

    if user_id in user_settings and user_settings[user_id]["video_message_id"] == video_message_id:
        settings = user_settings[user_id]
        if settings["speed"] is None or settings["resolution"] is None:
            await event.answer("Please select both compression type and resolution before starting.".encode())
            return

        original_message = await bot.get_messages(event.chat_id, ids=video_message_id)
        if not original_message or not original_message.media:
            await event.answer("Original video not found.".encode())
            return

        try:
            # Remove settings buttons
            await event.edit("Processing video...", buttons=[])
            db.tasks += 1
            logging.info(f"Starting compression with settings: {settings}")
            await compress(event, settings["speed"], settings["resolution"], settings["fps"], settings["crf"])
            logging.info("Compression process initiated.")
        except Exception as e:
            logging.error(f"Error during compression initiation: {e}")
            await bot.send_message(event.chat_id, "An error occurred during video compression.".encode())
        finally:
            db.tasks -= 1
            if user_id in user_settings:
                del user_settings[user_id]
            logging.info(f"User settings for {user_id} cleared.")
    else:
        await event.answer("Invalid operation or settings expired.".encode())


@bot.on(events.NewMessage(incoming=True, pattern="/as_video", from_users=Config.WhiteList))
async def as_video(event):
    await db.set_upload_mode(doc=False)
    await bot.send_message(event.chat_id, "✅ **I Wɪʟʟ Uᴘʟᴏᴀᴅ Tʜᴇ Fɪʟᴇѕ Aѕ Vɪᴅᴇᴏѕ**".encode())


@bot.on(events.NewMessage(incoming=True, pattern="/as_document", from_users=Config.WhiteList))
async def as_document(event):
    await db.set_upload_mode(doc=True)
    await bot.send_message(event.chat_id, "✅ **I Wɪʟʟ Uᴘʟᴏᴀᴅ Tʜᴇ Fɪʟᴇѕ Aѕ Dᴏᴄᴜᴍᴇɴᴛѕ**".encode())


@bot.on(events.NewMessage(incoming=True, pattern="/speed", from_users=Config.WhiteList))
async def set_speed_command(event):
    await bot.send_message(event.chat_id, "Use the settings menu after sending a video to select compression speed.".encode())


@bot.on(events.NewMessage(incoming=True, pattern="/crf", from_users=Config.WhiteList))
async def set_crf_command(event):
    await bot.send_message(event.chat_id, "Use the settings menu after sending a video to select CRF.".encode())


@bot.on(events.NewMessage(incoming=True, pattern="/fps", from_users=Config.WhiteList))
async def set_fps_command(event):
    await bot.send_message(event.chat_id, "Use the settings menu after sending a video to select FPS.".encode())


@bot.on(events.NewMessage(incoming=True, func=lambda e: e.photo, from_users=Config.WhiteList))
async def set_thumb(event):
    await bot.download_media(event.message, Config.Thumb)
    await db.set_thumb(original=False)
    await event.reply("✅ **Tʜᴜᴍʙɴᴀɪʟ Cʜᴀɴɢᴇᴅ**".encode())


@bot.on(events.NewMessage(incoming=True, pattern="/original_thumb", from_users=Config.WhiteList))
async def original_thumb(event):
    await db.set_thumb(original=True)
    await event.reply("✅ **ɪ Wɪʟʟ Uѕᴇ Oʀɪɢɪɴᴀʟ Tʜᴜᴍʙɴᴀɪʟ**".encode())


@bot.on(events.NewMessage(incoming=True, pattern="/original_fps", from_users=Config.WhiteList))
async def original_fps(event):
    await db.set_fps(None)
    await event.reply("✅ **I Wɪʟʟ Uѕᴇ Oʀɪɢɪɴᴀʟ FPS**".encode())


@bot.on(events.NewMessage(incoming=True, pattern="/commands", from_users=Config.WhiteList))
async def commands(event):
    await event.reply("🤖 **Vɪᴅᴇᴏ Cᴏᴍᴘʀᴇѕѕɪᴏɴ Sᴇᴛᴛɪɴɢѕ**:\n\nSend a video to access the settings menu.".encode())


@bot.on(events.CallbackQuery())
async def callback_handler(event):
    if event.sender_id not in Config.WhiteList:
        await event.answer("⛔️ Ꮪᴏʀʀʏ, Ꭲʜɪѕ Ᏼᴏᴛ Fᴏʀ Ꮲᴇʀѕᴏɴᴀʟ Uѕᴇ !! ⛔️".encode())
        return
    # Existing callback handlers for settings menu
    if event.data == b"settings":
        await settingscallback(event)
    elif event.data == b"compress":
        await compresscallback(event)
    elif event.data == b"options":
        await optionscallback(event)
    elif event.data == b"back":
        await backcallback(event)
    elif event.data == b"back_options":
        await backoptionscallback(event)
    elif event.data == b"back_compress":
        await backcompresscallback(event)
    # No need for individual speed callbacks here anymore
    elif event.data == b"crf":
        await crfcallback(event)
    elif event.data == b"fps":
        await fpscallback(event)
    elif event.data.startswith(b"crf_"):
        # Handle old CRF callbacks (consider removing if not needed)
        crf_value = event.data.decode().split("_")[1]
        await db.set_crf(crf_value)
        await event.answer(f"✅ CRF Ꮪᴇᴛ Ꭲᴏ {crf_value}".encode())
    elif event.data.startswith(b"fps_"):
        # Handle old FPS callbacks (consider removing if not needed)
        fps_value = event.data.decode().split("_")[1]
        await db.set_fps(fps_value)
        await event.answer(f"✅ FPS Ꮪᴇᴛ Ꭲᴏ {fps_value}".encode())


@bot.on(events.NewMessage(incoming=True, pattern="/start"))
async def start_handler(event):
    if event.sender_id not in Config.WhiteList:
        await event.reply("Ꮪᴏʀʀʏ, Ꭲʜɪѕ Ᏼᴏᴛ Fᴏʀ Ꮲᴇʀѕᴏɴᴀʟ Uѕᴇ\n\n**Yᴏᴜ Aʀᴇ Nᴏᴛ Aᴜᴛʜᴏʀɪᴢᴇᴅ Tᴏ Uѕᴇ Tʜɪѕ Bᴏᴛ!!**⛔️".encode())
        return
    settings = Button.inline("⚙ Sᴇᴛᴛɪɴgs", data="settings")
    developer = Button.url("Ꭰᴇᴠᴇʟᴏᴘᴇʀ 💫", url="https://t.me/A7_SYR")
    text = "Sᴇɴᴅ Mᴇ Aɴʏ Vɪᴅᴇᴏ Tᴏ Cᴏᴍᴘʀᴇѕѕ\n\nᏟʟɪᴄᴋ Ᏼᴜᴛᴛᴏɴ ⚙ Sᴇᴛᴛɪɴgs".encode()
    await event.reply(text, buttons=[[settings, developer]])


@bot.on(events.CallbackQuery(data=b"settings"))
async def settingscallback(event):
    buttons = [
        [Button.inline("⚙️ Compression Settings", data=b"main_settings")],
        [Button.inline("📤 Upload Options", data=b"upload_options")],
        [Button.inline("Back", data=b"back_main")]
    ]
    text = "**⚙️ Main Settings**".encode()
    await event.edit(text, buttons=buttons)


@bot.on(events.CallbackQuery(data=b"main_settings"))
async def main_settings_callback(event):
    buttons = [
        [Button.inline("⚡️ Speed", data=b"compress"),
         Button.inline("📊 CRF", data=b"crf"),
         Button.inline("🎬 FPS", data=b"fps")],
        [Button.inline("Back", data=b"settings")]
    ]
    text = "**⚙️ Compression Settings**".encode()
    await event.edit(text, buttons=buttons)


@bot.on(events.CallbackQuery(data=b"upload_options"))
async def upload_options_callback(event):
    as_video_button = Button.inline("📹 As Video", data=b"set_upload_video")
    as_document_button = Button.inline("📄 As Document", data=b"set_upload_document")
    original_thumb_button = Button.inline("🖼️ Original Thumbnail", data=b"original_thumb")
    change_thumb_button = Button.inline("📸 Change Thumbnail", data=b"change_thumb")
    back = Button.inline("Back", data=b"settings")
    text = "**📤 Upload Options**".encode()
    await event.edit(text, buttons=buttons)


@bot.on(events.CallbackQuery(data=b"set_upload_video"))
async def set_upload_video_callback(event):
    await db.set_upload_mode(doc=False)
    await event.answer("✅ Upload mode set to Video.".encode())


@bot.on(events.CallbackQuery(data=b"set_upload_document"))
async def set_upload_document_callback(event):
    await db.set_upload_mode(doc=True)
    await event.answer("✅ Upload mode set to Document.".encode())


@bot.on(events.CallbackQuery(data=b"change_thumb"))
async def change_thumb_callback(event):
    await event.answer("🖼️ Send me a photo to set as thumbnail.".encode())


@bot.on(events.CallbackQuery(data=b"back_main"))
async def back_main_callback(event):
    settings = Button.inline("⚙ Sᴇᴛᴛɪɴgs", data=b"settings")
    developer = Button.url("Ꭰᴇᴠᴇʟᴏᴘᴇʀ 💫", url="https://t.me/A7_SYR")
    text = "**Sᴇɴᴅ Mᴇ Aɴʏ Vɪᴅᴇᴏ Tᴏ Cᴏᴍᴘʀᴇѕѕ**\n\nᏟʟɪᴄᴋ Ᏼᴜᴛᴛᴏɴ **⚙ Sᴇᴛᴛɪɴgs**\n\nᏴᴇғᴏʀᴇ Ꮪᴇɴᴅɪɴɢ Ꭲʜᴇ Ꮩɪᴅᴇᴏ ғᴏʀ Ꮯᴏᴍᴘʀᴇѕѕɪᴏɴ\n👇".encode()
    await event.edit(text, buttons=[[settings, developer]])


@bot.on(events.CallbackQuery(data=b"back_options"))
async def backoptionscallback(event):
    compress_button = Button.inline("⚙️ Compression Settings", data=b"main_settings")
    upload_options = Button.inline("📤 Upload Options", data=b"upload_options")
    back = Button.inline("Back", data=b"back_main")
    text = "**⚙️ Main Settings**".encode()
    await event.edit(text, buttons=[[compress_button], [upload_options], [back]])


@bot.on(events.CallbackQuery(data=b"compress"))
async def compresscallback(event):
    speeds = {"Ultra Fast": "ultrafast", "Very Fast": "veryfast", "Faster": "faster", "Fast": "fast", "Medium": "medium", "Slow": "slow"}
    buttons = [
        [Button.inline(name, data=f"set_speed_global:{value}".encode()) for name, value in speeds.items() if i % 2 == 0],
        [Button.inline(name, data=f"set_speed_global:{value}".encode()) for i, (name, value) in enumerate(speeds.items()) if i % 2 != 0],
        [Button.inline("Back", data=b"main_settings")]
    ]
    text = "**Select Compression Speed**".encode()
    await event.edit(text, buttons=buttons)


@bot.on(events.CallbackQuery(pattern=r"set_speed_global:(.+?)".encode()))
async def set_global_speed_callback(event):
    speed_value = event.pattern_match.group(1).decode()
    await db.set_speed(speed_value)
    await event.answer(f"✅ Speed set to {speed_value.replace('fast', ' Fast').title()}⚡".encode())


@bot.on(events.CallbackQuery(data=b"back_compress"))
async def backcompresscallback(event):
    compress_button = Button.inline("⚡️ Speed", data=b"compress")
    crf_button = Button.inline("📊 CRF", data=b"crf")
    fps_button = Button.inline("🎬 FPS", data=b"fps")
    back = Button.inline("Back", data=b"settings")
    text = "**⚙️ Compression Settings**".encode()
    await event.edit(text, buttons=[[compress_button, crf_button, fps_button], [back]])


@bot.on(events.CallbackQuery(data=b"crf"))
async def crfcallback(event):
    crf_values = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
    buttons = [Button.inline(str(val), data=f"set_global_crf:{val}".encode()) for val in crf_values]
    back = Button.inline("Back", data=b"main_settings")
    text = "**Select Compression Ratio (CRF)**\nLower values mean higher quality.".encode()
    await event.edit(text, buttons=[buttons[:3], buttons[3:6], buttons[6:9], buttons[9:], [back]])


@bot.on(events.CallbackQuery(data=b"fps"))
async def fpscallback(event):
    fps_values = ["Original", 24, 25, 30, 45, 60]
    buttons = [Button.inline(str(val), data=f"set_global_fps:{val}".encode()) for val in fps_values]
    back = Button.inline("Back", data=b"main_settings")
    text = "**Select Frames Per Second (FPS)**".encode()
    await event.edit(text, buttons=[buttons[:3], buttons[3:], [back]])


@bot.on(events.CallbackQuery(pattern=r"set_global_(crf|fps):(.+?)".encode()))
async def set_global_setting_callback(event):
    setting_type = event.pattern_match.group(1).decode()
    value = event.pattern_match.group(2).decode()

    if setting_type == "crf":
        await db.set_crf(int(value))
        await event.answer(f"✅ Global CRF set to {value}".encode())
    elif setting_type == "fps":
        fps = int(value) if value.isdigit() else None
        await db.set_fps(fps)
        await event.answer(f"✅ Global FPS set to {value}".encode())


bot.loop.run_until_complete(db.init())
print("Bot-Started")
bot.run_until_disconnected()
