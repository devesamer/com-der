import logging
from telethon import Button
from telethon import events
from telethon.tl.functions.messages import EditMessageRequest
from telethon.tl.custom.message import Message

from main.database import db
from main.client import bot
from main.config import Config
from main.utils import compress as original_compress  # Rename to avoid conflict

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)

user_video_data = {}

async def compress(event, resolution=None, width=None, height=None):
    msg: Message = event.message
    in_path = await bot.download_media(msg.media)
    FT = in_path.split('-')[1].split('.')[0]
    out_path = f"{in_path.replace(FT, f'{FT}-compressed')}"
    progress = f"progress-{FT}.txt"
    fps = f" -r {db.fps}" if db.fps else ""
    scale_option = ""
    if resolution:
        if resolution == '240p':
            scale_option = ' -vf scale=426:240'
        elif resolution == '360p':
            scale_option = ' -vf scale=640:360'
        elif resolution == '480p':
            scale_option = ' -vf scale=854:480'
        elif resolution == '720p':
            scale_option = ' -vf scale=1280:720'
        elif resolution == '1080p':
            scale_option = ' -vf scale=1920:1080'
    elif width is not None and height is not None:
        scale_option = f' -vf scale={width}:{height}'

    cmd = (f'ffmpeg -hide_banner -loglevel quiet'
           f' -progress {progress} -i """{in_path}"""'
           f' -preset {db.speed} -vcodec libx265 -crf {db.crf}'
           f'{fps}{scale_option} -acodec copy -c:s copy """{out_path}""" -y')
    try:
        await event.reply("⚙️ **Compressing video...**")
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        while True:
            progress_file = None
            try:
                with open(progress, 'r') as f:
                    progress_data = f.read()
                    duration_match = re.search(r'Duration: (\d{2}:\d{2}:\d{2}\.\d{2})', progress_data)
                    time_match = re.search(r'out_time=(\d{2}:\d{2}:\d{2}\.\d{6})', progress_data)
                    if duration_match and time_match:
                        duration_str = duration_match.group(1)
                        time_str = time_match.group(1)
                        duration = sum(float(x) * 60 ** i for i, x in enumerate(reversed(duration_str.split(':'))))
                        time = sum(float(x) * 60 ** i for i, x in enumerate(reversed(time_str.split(':'))))
                        percentage = (time / duration) * 100
                        await bot.edit_message(event.chat_id, event.message.id + 1, f"⚙️ **Compressing video...**\n📊 **Progress:** {percentage:.2f}%")
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"Error reading progress: {e}")

            if process.returncode is not None:
                break
            await asyncio.sleep(1)

        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            await bot.send_file(event.chat_id, out_path, caption="✅ **Compressed video**")
        else:
            await bot.send_message(event.chat_id, f"❌ **Compression failed.**\n\n`{stderr.decode()}`")
    except Exception as e:
        await bot.send_message(event.chat_id, f"❌ **An error occurred during compression:**\n\n`{e}`")
    finally:
        import os
        if os.path.exists(in_path):
            os.remove(in_path)
        if os.path.exists(out_path):
            os.remove(out_path)
        if os.path.exists(progress):
            os.remove(progress)
        db.tasks -= 1


@bot.on(events.NewMessage(incoming=True, from_users=Config.WhiteList))
async def video_handler(event: events.NewMessage.Event):
    msg: Message = event.message
    if not event.is_private or not event.media or not hasattr(msg.media, "document"):
        return
    if 'video' not in msg.media.document.mime_type:
        return
    if db.tasks >= Config.Max_Tasks:
        await bot.send_message(event.chat_id, f"💢 **Tʜᴇʀᴇ Aʀᴇ** {Config.Max_Tasks} **Tᴀѕᴋѕ Wᴏʀᴋɪɴɢ Nᴏᴡ**")
        return

    user_id = event.sender_id
    user_video_data[user_id] = {'media': msg.media, 'chat_id': event.chat_id, 'reply_to': event.message.id}

    buttons = [
        [Button.inline("240p", data=f"resolution:240p:{user_id}"),
         Button.inline("360p", data=f"resolution:360p:{user_id}")],
        [Button.inline("480p", data=f"resolution:480p:{user_id}"),
         Button.inline("720p", data=f"resolution:720p:{user_id}")],
        [Button.inline("1080p", data=f"resolution:1080p:{user_id}")],
        [Button.inline("Custom", data=f"resolution:custom:{user_id}")]
    ]
    await bot.send_message(event.chat_id, "⚙️ **Choose video resolution:**", buttons=buttons, reply_to=event.message.id)

@bot.on(events.CallbackQuery(pattern=r"resolution:(.*):(.*)"))
async def resolution_callback(event):
    if event.sender_id not in Config.WhiteList:
        await event.answer("⛔️ Ꮪᴏʀʀʏ, Ꭲʜɪѕ Ᏼᴏᴛ Fᴏʀ Ꮲᴇʀѕᴏɴᴀʟ Uѕᴇ !! ⛔️")
        return
    resolution_type, user_id_str = event.data_match.group(1, 2)
    user_id = int(user_id_str)
    if event.sender_id != user_id:
        return await event.answer("This button is not for you!")

    if user_id not in user_video_data:
        return await event.answer("Video data not found. Please send the video again.")

    video_info = user_video_data[user_id]
    chat_id = video_info['chat_id']
    reply_to = video_info['reply_to']

    await event.answer(f"Selected resolution: {resolution_type}")

    if resolution_type == 'custom':
        await bot.send_message(chat_id, "📏 **Enter custom width and height (e.g., 640x480):**", reply_to=reply_to)
        await bot.add_event_handler(custom_resolution_handler, events.NewMessage(from_users=user_id, chats=chat_id, func=lambda e: e.reply_to_msg_id == reply_to + 1))
    else:
        db.tasks += 1
        try:
            await compress(event, resolution=resolution_type)
        except Exception as e:
            print(e)
        finally:
            if user_id in user_video_data:
                del user_video_data[user_id]
            db.tasks -= 1

async def custom_resolution_handler(event: events.NewMessage.Event):
    user_id = event.sender_id
    if user_id not in user_video_data:
        return await event.reply("Video data not found. Please send the video again.")

    resolution_input = event.text.strip()
    match = re.match(r'(\d+)x(\d+)', resolution_input)
    if match:
        width = int(match.group(1))
        height = int(match.group(2))
        db.tasks += 1
        try:
            await compress(event, width=width, height=height)
        except Exception as e:
            print(e)
        finally:
            if user_id in user_video_data:
                del user_video_data[user_id]
            db.tasks -= 1
    else:
        await event.reply("⚠️ **Invalid custom resolution format.** Please enter width and height like `640x480`.")
        await bot.add_event_handler(custom_resolution_handler, events.NewMessage(from_users=user_id, chats=event.chat_id, func=lambda e: e.reply_to_msg_id == event.message.id))

@bot.on(events.NewMessage(incoming=True, pattern="/as_video", from_users=Config.WhiteList))
async def as_video(event):
    await db.set_upload_mode(doc=False)
    await bot.send_message(event.chat_id, "✅ **I Wɪʟʟ Uᴘʟᴏᴀᴅ Tʜᴇ Fɪʟᴇѕ Aѕ Vɪᴅᴇᴏѕ**")

@bot.on(events.NewMessage(incoming=True, pattern="/as_document", from_users=Config.WhiteList))
async def as_video(event):
    await db.set_upload_mode(doc=True)
    await bot.send_message(event.chat_id, "✅ **I Wɪʟʟ Uᴘʟᴏᴀᴅ Tʜᴇ Fɪʟᴇѕ Aѕ Dᴏᴄᴜᴍᴇɴᴛѕ**")

@bot.on(events.NewMessage(incoming=True, pattern="/speed", from_users=Config.WhiteList))
async def set_crf(event):
    msg: Message = event.message
    parts = msg.text.split()
    if len(parts) != 2:
        await bot.send_message(event.chat_id, "🚀**Sᴇʟᴇᴄᴛɪᴏɴ Oғ Cᴏᴍᴘʀᴇѕѕɪᴏɴ Sᴘᴇᴇᴅ**\n\n "
                                              "`/speed veryfast` \n\n`/speed fast`\n\n`/speed ultrafast`")
    else:
        await db.set_speed(parts[1])
        await bot.send_message(event.chat_id, "✅ **Dᴏɴᴇ**")

@bot.on(events.NewMessage(incoming=True, pattern="/crf", from_users=Config.WhiteList))
async def set_crf(event):
    msg: Message = event.message
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isnumeric():
        await bot.send_message(event.chat_id, "⚡️ **Sᴇʟᴇᴄᴛɪᴏɴ Oғ Cᴏᴍᴘʀᴇѕѕɪᴏɴ Rᴀᴛɪᴏ**\n\n `/crf 28`    ↩ ↪   `/crf 27`")
    else:
        await db.set_crf(int(parts[1]))
        await bot.send_message(event.chat_id, "✅ **Dᴏɴᴇ**")

@bot.on(events.NewMessage(incoming=True, pattern="/fps", from_users=Config.WhiteList))
async def set_fps(event):
    msg: Message = event.message
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isnumeric():
        await bot.send_message(event.chat_id, "💢 **Iɴᴠᴀʟɪᴅ SʏɴᴛᴀX**\n**Eхᴀᴍᴘʟᴇ**: `/fps 24`")
    else:
        await db.set_fps(int(parts[1]))
        await bot.send_message(event.chat_id, "✅ **Dᴏɴᴇ**")

@bot.on(events.NewMessage(incoming=True, func=lambda e: e.photo, from_users=Config.WhiteList))
async def set_thumb(event):
    await bot.download_media(event.message, Config.Thumb)
    await db.set_thumb(original=False)
    await event.reply("✅ **Tʜᴜᴍʙɴᴀɪʟ Cʜᴀɴɢᴇᴅ**")

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
    if event.data == "settings":
        await settings_handler(event)

@bot.on(events.NewMessage(incoming=True, pattern="/start"))
async def start_handler(event):
    if event.sender_id not in Config.WhiteList:
        await event.reply("Ꮪᴏʀʀʏ, Ꭲʜɪѕ Ᏼᴏᴛ Fᴏʀ Ꮲᴇʀѕᴏɴᴀʟ Uѕᴇ\n\n**Yᴏᴜ Aʀᴇ Nᴏᴛ Aᴜᴛʜᴏʀɪᴢᴇᴅ Tᴏ Uѕᴇ Tʜɪѕ Bᴏᴛ!!**⛔️")
        return
    settings = Button.inline("⚙ Sᴇᴛᴛɪɴgs", data="settings")
    developer = Button.url("Ꭰᴇᴠᴇʟᴏᴘᴇʀ 💫", url="https://t.me/A7_SYR")
    text = "Sᴇɴᴅ Mᴇ Aɴʏ Vɪᴅᴇᴏ Tᴏ Cᴏᴍᴘʀᴇѕѕ\n\nᏟʟɪᴄᴋ Ᏼᴜᴛᴛᴏɴ ⚙ Sᴇᴛᴛɪɴgs"
    await event.reply(text, buttons=[[settings, developer]])

@bot.on(events.CallbackQuery(data="settings"))
async def settingscallback(event):
    compress_button = Button.inline("⚙️ Resolution & Compress", data="resolution_compress")
    options = Button.inline("⚙️ Extra Options", data="options")
    back = Button.inline("⬅️ Back", data="back")
    text = "**⚙️ Select Setting ⚙️**"
    await event.edit(text, buttons=[[compress_button, options], [back]])

@bot.on(events.CallbackQuery(data="resolution_compress"))
async def resolution_compress_callback(event):
    back = Button.inline("⬅️ Back", data="back_settings")
    text = "**⚙️ Resolution & Compression Settings ⚙️**\n\nSend me a video to set resolution!"
    await event.edit(text, buttons=[back])

@bot.on(events.CallbackQuery(data="options"))
async def optionscallback(event):
    crf = Button.inline("⚡️ Compression Ratio (CRF)", data="crf")
    fps = Button.inline("🎬 Frames Per Second (FPS)", data="fps")
    back = Button.inline("⬅️ Back", data="back_settings")
    text = "**⚙️ Extra Options ⚙️**\n\nSet these options using the buttons below or by sending commands."
    await event.edit(text, buttons=[[crf, fps], [back]])

@bot.on(events.CallbackQuery(data="back"))
async def backcallback(event):
    settings = Button.inline("⚙ Sᴇᴛᴛɪɴgs", data="settings")
    developer = Button.url("Ꭰᴇᴠᴇʟᴏᴘᴇʀ 💫", url="https://t.me/A7_SYR")
    text = "**Send Me Any Video To Compress**\n\nClick Button **⚙ Sᴇᴛᴛɪɴgs**\n\nBefore Sending The Video for Compression\n👇"
    await event.edit(text, buttons=[[settings, developer]])

@bot.on(events.CallbackQuery(data="back_settings"))
async def backsettingscallback(event):
    settings = Button.inline("⚙ Sᴇᴛᴛɪɴgs", data="settings")
    developer = Button.url("Ꭰᴇᴠᴇʟᴏᴘᴇʀ 💫", url="https://t.me/A7_SYR")
    text = "**Send Me Any Video To Compress**\n\nClick Button **⚙ Sᴇᴛᴛɪɴgs**\n\nBefore Sending The Video for Compression\n👇"
    await event.edit(text, buttons=[[settings, developer]])

@bot.on(events.CallbackQuery(data="crf"))
async def crfcallback(event):
    crf_values = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
    buttons = [Button.inline(str(val), data=f"set_crf:{val}") for val in crf_values]
    back = Button.inline("⬅️ Back", data="back_options")
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([back])
    text = "**⚙️ Select Compression Ratio (CRF)**\n\nLower values mean better quality but larger file size."
    await event.edit(text, buttons=rows)

@bot.on(events.CallbackQuery(data=re.compile(r"set_crf:(\d+)")))
async def set_crf_callback(event):
    crf_value = event.data_match.group(1)
    await db.set_crf(int(crf_value))
    await event.answer(f"✅ CRF set to {crf_value}")

@bot.on(events.CallbackQuery(data="fps"))
async def fpscallback(event):
    fps_values = [30, 45, 60]
    buttons = [Button.inline(str(val), data=f"set_fps:{val}") for val in fps_values]
    back = Button.inline("⬅️ Back", data="back_options")
    text = "**⚙️ Select Frames Per Second (FPS)**"
    await event.edit(text, buttons=[buttons, [back]])

@bot.on(events.CallbackQuery(data=re.compile(r"set_fps:(\d+)")))
async def set_fps_callback(event):
    fps_value = event.data_match.group(1)
    await db.set_fps(int(fps_value))
    await event.answer(f"✅ FPS set to {fps_value}")

bot.loop.run_until_complete(db.init())
print("Bot-Started")
bot.run_until_disconnected()
