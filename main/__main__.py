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
    try:
        db.tasks += 1
        await compress(event)
    except Exception as e:
        print(e)
    finally:
        db.tasks -= 1


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
        await bot.send_message(event.chat_id, "💢 **Iɴᴠᴀʟɪᴅ Sʏɴᴛᴀх**\n**Eхᴀᴍᴘʟᴇ**: `/fps 24`")
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
    settings = Button.inline("⚙ Sᴇᴛᴛɪɴɢs", data="settings")
    developer = Button.url("Ꭰᴇᴠᴇʟᴏᴘᴇʀ 💫", url="https://t.me/A7_SYR")
    text = "Sᴇɴᴅ Mᴇ Aɴʏ Vɪᴅᴇᴏ Tᴏ Cᴏᴍᴘʀᴇѕѕ\n\nᏟʟɪᴄᴋ Ᏼᴜᴛᴛᴏɴ ⚙ Sᴇᴛᴛɪɴɢѕ"
    await event.reply(text, buttons=[[settings, developer]])

@bot.on(events.CallbackQuery(data="settings"))
async def settingscallback(event):
    compress = Button.inline("Ꮯᴏᴍᴘʀᴇѕѕɪᴏɴ Ꮪᴘᴇᴇᴅ ⚡", data="compress")
    options = Button.inline("Ꭼхᴛʀᴀ Oᴘᴛɪᴏɴѕ ✨", data="options")
    back = Button.inline("Ᏼᴀᴄᴋ", data="back")
    text = "**⚙ Sᴇʟᴇᴄᴛ Sᴇᴛᴛɪɴɢ ⚙**"
    await event.edit(text, buttons=[[compress, options], [back]])

@bot.on(events.CallbackQuery(data="compress"))
async def compresscallback(event):
    back = Button.inline("Ᏼᴀᴄᴋ", data="back_compress")
    text = "**Sᴇᴛᴛɪɴɢ Cᴏᴍᴘʀᴇѕѕ Oᴘᴛɪᴏɴѕ**⚡"
    await event.edit(text, buttons=[back])

@bot.on(events.CallbackQuery(data="options"))
async def optionscallback(event):
    back = Button.inline("Ᏼᴀᴄᴋ", data="back_options")
    text = "**Ꭼхᴛʀᴀ Oᴘᴛɪᴏɴѕ **✨"
    await event.edit(text, buttons=[back])

@bot.on(events.CallbackQuery(data="back"))
async def backcallback(event):
    settings = Button.inline("⚙ Sᴇᴛᴛɪɴɢs", data="settings")
    developer = Button.url("Ꭰᴇᴠᴇʟᴏᴘᴇʀ 💫", url="https://t.me/A7_SYR")
    text = "**Sᴇɴᴅ Mᴇ Aɴʏ Vɪᴅᴇᴏ Tᴏ Cᴏᴍᴘʀᴇѕѕ**\n\nᏟʟɪᴄᴋ Ᏼᴜᴛᴛᴏɴ **⚙ Sᴇᴛᴛɪɴɢѕ**\n\nᏴᴇғᴏʀᴇ Ꮪᴇɴᴅɪɴɢ Ꭲʜᴇ Ꮩɪᴅᴇᴏ ғᴏʀ Ꮯᴏᴍᴘʀᴇѕѕɪᴏɴ\n👇"
    await event.edit(text, buttons=[settings, developer])

@bot.on(events.CallbackQuery(data="back_options"))
async def backoptionscallback(event):
    compress = Button.inline("Ꮯᴏᴍᴘʀᴇѕѕɪᴏɴ Ꮪᴘᴇᴇᴅ ⚡", data="compress")
    options = Button.inline("Ꭼхᴛʀᴀ Oᴘᴛɪᴏɴѕ ✨", data="options")
    back = Button.inline("Ᏼᴀᴄᴋ", data="back")
    text = "**⚙  Sᴇʟᴇᴄᴛ Sᴇᴛᴛɪɴɢ  ⚙**"
    await event.edit(text, buttons=[[compress, options], [back]])

@bot.on(events.CallbackQuery(data="compress"))
async def compresscallback(event):
    ultrafast = Button.inline("Uʟᴛʀᴀғᴀѕᴛ", data="ultrafast")
    veryfast = Button.inline("Ꮩᴇʀʏғᴀѕᴛ", data="veryfast")
    faster = Button.inline("Fᴀѕᴛᴇʀ", data="faster")
    fast = Button.inline("Fᴀѕᴛ", data="fast")
    medium = Button.inline("Ꮇᴇᴅɪᴜᴍ", data="medium")
    slow = Button.inline("Ꮪʟᴏᴡ", data="slow")
    back = Button.inline("Ᏼᴀᴄᴋ", data="back_compress")
    text = "**Sᴇʟᴇᴄᴛ Cᴏᴍᴘʀᴇѕѕɪᴏɴ Sᴘᴇᴇᴅ**"
    await event.edit(text, buttons=[[ultrafast, veryfast], [faster, fast], [medium, slow], [back]])

@bot.on(events.CallbackQuery(data="ultrafast"))
async def ultrafastcallback(event):
    await db.set_speed("ultrafast")
    await event.answer("✅ Ꮪᴘᴇᴇᴅ Ꮪᴇᴛ Ꭲᴏ Uʟᴛʀᴀғᴀѕᴛ⚡")

@bot.on(events.CallbackQuery(data="veryfast"))
async def veryfastcallback(event):
    await db.set_speed("veryfast")
    await event.answer("✅ Ꮪᴘᴇᴇᴅ Ꮪᴇᴛ Ꭲᴏ Ꮩᴇʀʏғᴀѕᴛ⚡")

@bot.on(events.CallbackQuery(data="faster"))
async def fastercallback(event):
    await db.set_speed("faster")
    await event.answer("✅ Ꮪᴘᴇᴇᴅ Ꮪᴇᴛ Ꭲᴏ Fᴀѕᴛᴇʀ⚡")

@bot.on(events.CallbackQuery(data="fast"))
async def fastcallback(event):
    await db.set_speed("fast")
    await event.answer("✅ Ꮪᴘᴇᴇᴅ Ꮪᴇᴛ Ꭲᴏ Fᴀѕᴛ⚡")

@bot.on(events.CallbackQuery(data="medium"))
async def mediumcallback(event):
    await db.set_speed("medium")
    await event.answer("✅ Ꮪᴘᴇᴇᴅ Ꮪᴇᴛ Ꭲᴏ Ꮇᴇᴅɪᴜᴍ")

@bot.on(events.CallbackQuery(data="slow"))
async def slowcallback(event):
    await db.set_speed("slow")
    await event.answer("✅ Ꮪᴘᴇᴇᴅ Ꮪᴇᴛ Ꭲᴏ Ꮪʟᴏᴡ")

@bot.on(events.CallbackQuery(data="back_compress"))
async def backcompresscallback(event):
    compress = Button.inline("Ꮯᴏᴍᴘʀᴇѕѕɪᴏɴ Ꮪᴘᴇᴇᴅ", data="compress")
    options = Button.inline("Ꭼхᴛʀᴀ Oᴘᴛɪᴏɴѕ", data="options")
    back = Button.inline("Ᏼᴀᴄᴋ", data="back")
    text = "**Sᴇʟᴇᴄᴛ Sᴇᴛᴛɪɴɢ**"
    await event.edit(text, buttons=[[compress, options], [back]])

@bot.on(events.CallbackQuery(data="options"))
async def optionscallback(event):
    crf = Button.inline("Ꮯᴏᴍᴘʀᴇѕѕɪᴏɴ Rᴀᴛɪᴏ (CRF)", data="crf")
    fps = Button.inline("Fʀᴀᴍᴇs Ꮲᴇʀ Ꮪᴇᴄᴏɴᴅ (FPS)", data="fps")
    back = Button.inline("Ᏼᴀᴄᴋ", data="back_options")
    text = "**Sᴇɴᴅ Mᴇ** Ꭲᴏ Ꮪᴇᴛ\n\n/as_video   **Uᴘʟᴏᴀᴅ Aѕ Vɪᴅᴇᴏ 📹**\n\n/original_thumb  **Dᴇғᴀᴜʟᴛ Tʜᴜᴍʙɴᴀɪʟ**\n\n\n**🖼 Sᴇɴᴅ Aɴʏ Pɪᴄᴛᴜʀᴇ Tᴏ Sᴇᴛ Iᴛ Aѕ Tʜᴜᴍʙɴᴀɪʟ**"
    await event.edit(text, buttons=[[crf], [fps], [back]])

@bot.on(events.CallbackQuery(data="crf"))
async def crfcallback(event):
    crf_20 = Button.inline("20", data="crf_20")
    crf_21 = Button.inline("21", data="crf_21")
    crf_22 = Button.inline("22", data="crf_22")
    crf_23 = Button.inline("23", data="crf_23")
    crf_24 = Button.inline("24", data="crf_24")
    crf_25 = Button.inline("25", data="crf_25")
    crf_26 = Button.inline("26", data="crf_26")
    crf_27 = Button.inline("27", data="crf_27")
    crf_28 = Button.inline("28", data="crf_28")
    crf_29 = Button.inline("29", data="crf_29")
    crf_30 = Button.inline("30", data="crf_30")
    back = Button.inline("Ᏼᴀᴄᴋ", data="back_options")
    text = "**Sᴇʟᴇᴄᴛ Cᴏᴍᴘʀᴇѕѕɪᴏɴ Rᴀᴛɪᴏ** (CRF)"
    await event.edit(text, buttons=[[crf_20, crf_21, crf_22], [crf_23, crf_24, crf_25], [crf_26, crf_27, crf_28], [crf_29, crf_30], [back]])

@bot.on(events.CallbackQuery(data="fps"))
async def fpscallback(event):
    fps_30 = Button.inline("30", data="fps_30")
    fps_45 = Button.inline("45", data="fps_45")
    fps_60 = Button.inline("60", data="fps_60")
    back = Button.inline("Ᏼᴀᴄᴋ", data="back_options")
    text = "**Sᴇʟᴇᴄᴛ Fʀᴀᴍᴇs Pᴇʀ Sᴇᴄᴏɴᴅ** (FPS)\n\n**Sᴇɴᴅ Mᴇ**  /original_fps\n\nᎢᴏ Ꮪᴇᴛ   Ꭰᴇғᴀᴜʟᴛ FᏢᏚ"
    await event.edit(text, buttons=[[fps_30, fps_45], [fps_60], [back]])

@bot.on(events.CallbackQuery(data="crf_20"))
async def crf20callback(event):
    await db.set_crf("20")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 20")

@bot.on(events.CallbackQuery(data="crf_21"))
async def crf21callback(event):
    await db.set_crf("21")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 21")

@bot.on(events.CallbackQuery(data="crf_22"))
async def crf22callback(event):
    await db.set_crf("22")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 22")

@bot.on(events.CallbackQuery(data="crf_23"))
async def crf23callback(event):
    await db.set_crf("23")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 23")

@bot.on(events.CallbackQuery(data="crf_24"))
async def crf24callback(event):
    await db.set_crf("24")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 24")

@bot.on(events.CallbackQuery(data="crf_25"))
async def crf25callback(event):
    await db.set_crf("25")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 25")

@bot.on(events.CallbackQuery(data="crf_26"))
async def crf26callback(event):
    await db.set_crf("26")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 26")

@bot.on(events.CallbackQuery(data="crf_27"))
async def crf27callback(event):
    await db.set_crf("27")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 27")

@bot.on(events.CallbackQuery(data="crf_28"))
async def crf28callback(event):
    await db.set_crf("28")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 28")

@bot.on(events.CallbackQuery(data="crf_29"))
async def crf29callback(event):
    await db.set_crf("29")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 29")

@bot.on(events.CallbackQuery(data="crf_30"))
async def crf30callback(event):
    await db.set_crf("30")
    await event.answer("✅ CRF Ꮪᴇᴛ Ꭲᴏ 30")

@bot.on(events.CallbackQuery(data="fps_30"))
async def fps30callback(event):
    await db.set_fps("30")
    await event.answer("✅ FPS Ꮪᴇᴛ Ꭲᴏ 30")

@bot.on(events.CallbackQuery(data="fps_45"))
async def fps45callback(event):
    await db.set_fps("45")
    await event.answer("✅ FPS Ꮪᴇᴛ Ꭲᴏ 45")

@bot.on(events.CallbackQuery(data="fps_60"))
async def fps60callback(event):
    await db.set_fps("60")
    await event.answer("✅ FPS Ꮪᴇᴛ Ꭲᴏ 60")


bot.loop.run_until_complete(db.init())
print("Bot-Started")
bot.run_until_disconnected()
