import logging
from telethon import Button
from telethon import events
from telethon.tl.functions.messages import EditMessageRequest
from telethon.tl.custom.message import Message
import os

from main.database import db
from main.client import bot
from main.config import Config
from main.utils import compress, get_video_metadata, download_from_url

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)


COMPRESSION_TYPES = {
    "high": {"crf": 23, "speed": "faster", "label": "High Quality 💎"},
    "medium": {"crf": 28, "speed": "fast", "label": "Medium Quality ⚙️"},
    "low": {"crf": 35, "speed": "ultrafast", "label": "Low Size 🚀"},
    "custom": {"label": "Custom Settings 🛠️"}
}

RESOLUTIONS = {
    "original": {"label": "Original 🎬", "scale": None},
    "240p": {"label": "240p", "scale": "426:240"},
    "360p": {"label": "360p", "scale": "640:360"},
    "480p": {"label": "480p", "scale": "854:480"},
    "720p": {"label": "720p", "scale": "1280:720"},
    "1080p": {"label": "1080p", "scale": "1920:1080"},
    "custom": {"label": "Custom", "scale": None}
}

FPS_VALUES = {
    "original": {"label": "Original", "value": None},
    "30": {"label": "30", "value": 30},
    "24": {"label": "24", "value": 24}
}

CRF_VALUES = {str(i): {"label": str(i), "value": i} for i in range(17, 36)} # نطاق قيم CRF

SPEED_VALUES = {
    "ultrafast": {"label": "Ultrafast ⚡️", "value": "ultrafast"},
    "veryfast": {"label": "Veryfast 💨", "value": "veryfast"},
    "faster": {"label": "Faster 🏃", "value": "faster"},
    "fast": {"label": "Fast 🚶", "value": "fast"},
    "medium": {"label": "Medium 🐌", "value": "medium"},
    "slow": {"label": "Slow 🐢", "value": "slow"}
}


@bot.on(events.NewMessage(incoming=True, from_users=Config.WhiteList))
async def main_handler(event: events.NewMessage.Event):
    msg: Message = event.message
    chat_id = event.chat_id

    # معالجة الروابط
    if msg.raw_text and ("http://" in msg.raw_text or "https://" in msg.raw_text):
        await handle_url(event)
        return

    # معالجة ملفات الفيديو
    if not event.is_private or not event.media or not hasattr(msg.media, "document"):
        return
    if 'video' not in msg.media.document.mime_type:
        return

    await show_compression_options(event)


async def show_compression_options(event):
    msg: Message = event.message
    chat_id = event.chat_id
    video_file = msg.media.document
    file_id = video_file.id

    metadata = await get_video_metadata(video_file, bot)
    if not metadata:
        await bot.send_message(chat_id, "⚠️ **Error: Could not retrieve video metadata.**")
        return

    codec = metadata.get("codec_name", "N/A")
    width = metadata.get("width", "N/A")
    height = metadata.get("height", "N/A")

    text = f"**Video Information:**\n"
    text += f"Codec: `{codec}`\n"
    text += f"Resolution: `{width}x{height}`\n\n"
    text += "**Choose Compression Settings:**"

    buttons = [
        [Button.inline("⚙️ Compression Type", data=f"select_compression_type:{file_id}")],
        [Button.inline("📐 Resolution", data=f"select_resolution:{file_id}")],
        [Button.inline("🎬 FPS & CRF", data=f"select_fps_crf:{file_id}")],
        [Button.inline("🚀 Execute Compression", data=f"execute_compression:{file_id}")],
        [Button.inline("🗑️ Cancel", data=f"cancel_compression:{file_id}")]
    ]

    await bot.send_message(chat_id, text, buttons=buttons, reply_to=msg.id)
    await db.set_video_data(chat_id, file_id, {"file_id": file_id})


async def handle_url(event):
    msg: Message = event.message
    chat_id = event.chat_id
    url = msg.raw_text.strip()

    reply_message = await bot.send_message(chat_id, f"📥 **Downloading video from:** `{url}`")
    try:
        file_path = await download_from_url(url)
        if file_path:
            await reply_message.edit(f"✅ **Video downloaded successfully!**\n\nNow, choose compression settings:")
            file_id = f"url_{hash(url)}" # إنشاء معرف فريد للرابط
            await db.set_video_data(chat_id, file_id, {"file_path": file_path})
            await show_compression_options_for_url(event, file_id)
        else:
            await reply_message.edit("⚠️ **Error: Could not download video from the provided URL.**")
    except Exception as e:
        await reply_message.edit(f"⚠️ **Error during download:** `{e}`")


async def show_compression_options_for_url(event, file_id):
    chat_id = event.chat_id

    text = "**Choose Compression Settings for the downloaded video:**"

    buttons = [
        [Button.inline("⚙️ Compression Type", data=f"select_compression_type_url:{file_id}")],
        [Button.inline("📐 Resolution", data=f"select_resolution_url:{file_id}")],
        [Button.inline("🎬 FPS & CRF", data=f"select_fps_crf_url:{file_id}")],
        [Button.inline("🚀 Execute Compression", data=f"execute_compression_url:{file_id}")],
        [Button.inline("🗑️ Cancel", data=f"cancel_compression_url:{file_id}")]
    ]

    await bot.send_message(chat_id, text, buttons=buttons)


@bot.on(events.CallbackQuery(pattern=r"cancel_compression:(.*)"))
async def cancel_compression(event):
    file_id = event.pattern_match.group(1)
    await event.edit("🚫 **Compression cancelled.**")
    await db.clear_video_data(event.chat_id, file_id)

@bot.on(events.CallbackQuery(pattern=r"execute_compression:(.*)"))
async def execute_compression(event):
    file_id = event.pattern_match.group(1)
    chat_id = event.chat_id
    video_data = await db.get_video_data(chat_id, file_id)
    if not video_data or not video_data.get("file_id"):
        await event.answer("⚠️ Please send a video first and select compression settings.", show_alert=True)
        return

    await event.edit("⏳ **Processing video with selected settings...**")
    try:
        db.tasks += 1
        await compress(event, video_data)
    except Exception as e:
        print(e)
        await event.edit(f"💢 **An error occurred during compression:** `{e}`")
    finally:
        db.tasks -= 1
        await db.clear_video_data(chat_id, file_id)


@bot.on(events.CallbackQuery(pattern=r"execute_compression_url:(.*)"))
async def execute_compression_url(event):
    file_id = event.pattern_match.group(1)
    chat_id = event.chat_id
    video_data = await db.get_video_data(chat_id, file_id)
    if not video_data or not video_data.get("file_path"):
        await event.answer("⚠️ Please send a video URL first and select compression settings.", show_alert=True)
        return

    await event.edit(f"⏳ **Processing downloaded video:** `{os.path.basename(video_data['file_path'])}` **with selected settings...**")
    try:
        db.tasks += 1
        await compress(event, video_data, input_path=video_data['file_path'])
    except Exception as e:
        print(e)
        await event.edit(f"💢 **An error occurred during compression:** `{e}`")
    finally:
        db.tasks -= 1
        await db.clear_video_data(chat_id, file_id)
        if video_data.get("file_path") and os.path.exists(video_data["file_path"]):
            os.remove(video_data["file_path"])

@bot.on(events.CallbackQuery(pattern=r"select_compression_type(?:_url)?:(.*)"))
async def select_compression_type(event):
    file_id = event.pattern_match.group(1)
    buttons = [[Button.inline(data["label"], data=f"set_compression_type:{file_id}:{name}")] for name, data in COMPRESSION_TYPES.items()]
    buttons.append([Button.inline("Back", data=f"back_to_main_options:{file_id}")])
    await event.edit("**Choose Compression Type:**", buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r"set_compression_type:(.*):(.*)"))
async def set_compression_type_callback(event):
    file_id = event.pattern_match.group(1)
    compression_type = event.pattern_match.group(2)
    chat_id = event.chat_id
    settings = COMPRESSION_TYPES.get(compression_type)
    if settings and compression_type != "custom":
        await db.update_video_data(chat_id, file_id, {"crf": settings["crf"], "speed": settings["speed"]})
        await event.answer(f"✅ Compression type set to: {settings['label']}")
    elif compression_type == "custom":
        await event.answer("🛠️ Choose custom settings from the other options.")
    await show_main_options(event, file_id)

async def show_main_options(event, file_id):
    text = "**Choose Compression Settings:**"
    buttons = [
        [Button.inline("⚙️ Compression Type", data=f"select_compression_type:{file_id}")],
        [Button.inline("📐 Resolution", data=f"select_resolution:{file_id}")],
        [Button.inline("🎬 FPS & CRF", data=f"select_fps_crf:{file_id}")],
        [Button.inline("🚀 Execute Compression", data=f"execute_compression:{file_id}")],
        [Button.inline("🗑️ Cancel", data=f"cancel_compression:{file_id}")]
    ]
    await event.edit(text, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r"back_to_main_options:(.*)"))
async def back_to_main_options(event):
    file_id = event.pattern_match.group(1)
    await show_main_options(event, file_id)

@bot.on(events.CallbackQuery(pattern=r"select_resolution(?:_url)?:(.*)"))
async def select_resolution(event):
    file_id = event.pattern_match.group(1)
    buttons = [[Button.inline(data["label"], data=f"set_resolution:{file_id}:{name}")] for name, data in RESOLUTIONS.items()]
    buttons.append([Button.inline("Back", data=f"back_to_main_options:{file_id}")])
    await event.edit("**Choose Resolution:**", buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r"set_resolution:(.*):(.*)"))
async def set_resolution_callback(event):
    file_id = event.pattern_match.group(1)
    resolution = event.pattern_match.group(2)
    chat_id = event.chat_id
    scale = RESOLUTIONS.get(resolution, {}).get("scale")
    await db.update_video_data(chat_id, file_id, {"resolution": resolution, "scale": scale})
    await event.answer(f"✅ Resolution set to: {RESOLUTIONS[resolution]['label']}")
    await show_main_options(event, file_id)

@bot.on(events.CallbackQuery(pattern=r"select_fps_crf(?:_url)?:(.*)"))
async def select_fps_crf(event):
    file_id = event.pattern_match.group(1)
    buttons = [
        [Button.inline("FPS", data=f"select_fps:{file_id}"),
         Button.inline("CRF", data=f"select_crf:{file_id}")],
        [Button.inline("Back", data=f"back_to_main_options:{file_id}")]
    ]
    await event.edit("**Choose FPS or CRF settings:**", buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r"select_fps:(.*)"))
async def select_fps(event):
    file_id = event.pattern_match.group(1)
    buttons = [[Button.inline(data["label"], data=f"set_fps:{file_id}:{name}")] for name, data in FPS_VALUES.items()]
    buttons.append([Button.inline("Back", data=f"select_fps_crf:{file_id}")])
    await event.edit("**Choose FPS:**", buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r"set_fps:(.*):(.*)"))
async def set_fps_callback(event):
    file_id = event.pattern_match.group(1)
    fps = FPS_VALUES.get(event.pattern_match.group(2), {}).get("value")
    chat_id = event.chat_id
    await db.update_video_data(chat_id, file_id, {"fps": fps})
    await event.answer(f"✅ FPS set to: {FPS_VALUES[event.pattern_match.group(2)]['label']}")
    await show_main_options(event, file_id)

@bot.on(events.CallbackQuery(pattern=r"select_crf:(.*)"))
async def select_crf(event):
    file_id = event.pattern_match.group(1)
    # Create buttons dynamically from CRF_VALUES
    buttons = []
    row = []
    for name, data in CRF_VALUES.items():
        row.append(Button.inline(data["label"], data=f"set_crf:{file_id}:{name}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([Button.inline("Back", data=f"select_fps_crf:{file_id}")])
    await event.edit("**Choose CRF (Compression Ratio):**\nLower values mean higher quality and larger file size.", buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r"set_crf:(.*):(.*)"))
async def set_crf_callback(event):
    file_id = event.pattern_match.group(1)
    crf = CRF_VALUES.get(event.pattern_match.group(2), {}).get("value")
    chat_id = event.chat_id
    await db.update_video_data(chat_id, file_id, {"crf": crf})
    await event.answer(f"✅ CRF set to: {CRF_VALUES[event.pattern_match.group(2)]['label']}")
    await show_main_options(event, file_id)


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
    if len(parts) != 2 or parts[1] not in SPEED_VALUES:
        await bot.send_message(event.chat_id, "🚀**Sᴇʟᴇᴄᴛɪᴏɴ Oғ Cᴏᴍᴘʀᴇѕѕɪᴏɴ Sᴘᴇᴇᴅ**\n\n" +
                                              "\n".join(f"`/speed {name}` - {data['label']}" for name, data in SPEED_VALUES.items()))
    else:
        await db.set_speed(SPEED_VALUES[parts[1]]['value'])
        await bot.send_message(event.chat_id, f"✅ **Speed set to:** {SPEED_VALUES[parts[1]]['label']}")


@bot.on(events.NewMessage(incoming=True, pattern="/crf", from_users=Config.WhiteList))
async def set_crf_command(event):
    msg: Message = event.message
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isnumeric() or parts[1] not in CRF_VALUES:
        await bot.send_message(event.chat_id, "⚡️ **Sᴇʟᴇᴄᴛɪᴏɴ Oғ Cᴏᴍᴘʀᴇѕѕɪᴏɴ Rᴀᴛɪᴏ**\n\n" +
                                              "\n".join(f"`/crf {name}` - Value: {data['value']}" for name, data in CRF_VALUES.items()))
    else:
        await db.set_crf(CRF_VALUES[parts[1]]['value'])
        await bot.send_message(event.chat_id, f"✅ **CRF set to:** {CRF_VALUES[parts[1]]['label']}")


@bot.on(events.NewMessage(incoming=True, pattern="/fps", from_users=Config.WhiteList))
async def set_fps_command(event):
    msg: Message = event.message
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isnumeric() or parts[1] not in [str(v['value']) for v in FPS_VALUES.values() if v['value'] is not None]:
        await bot.send_message(event.chat_id, "💢 **Iɴᴠᴀʟɪᴅ SʏɴᴛᴀX**\n**Eхᴀᴍᴘʟᴇ**: `/fps 24`\n\nAvailable FPS values:\n" +
                                              "\n".join(f"`/fps {data['value']}` - {data['label']}" for data in FPS_VALUES.values() if data['value'] is not None))
    else:
        await db.set_fps(int(parts[1]))
        await bot.send_message(event.chat_id, f"✅ **FPS set to:** {FPS_VALUES[parts[1]]['label']}")

