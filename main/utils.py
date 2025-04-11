from time import time
import asyncio
import math
import os
import re
import ffmpeg
import yt_dlp

from telethon import Button, events
from telethon.events import CallbackQuery
from telethon.tl.types import Message, DocumentAttributeFilename, DocumentAttributeVideo
from ethon.telefunc import fast_download, fast_upload
from ethon.pyfunc import video_metadata as ethon_video_metadata, total_frames as tf

from main.client import bot
from main.config import Config
from main.database import db


async def get_video_metadata(video_file, client):
    file_path = await client.download_media(video_file)
    if not file_path:
        return None
    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream:
            metadata = {
                'codec_name': video_stream.get('codec_name'),
                'width': video_stream.get('width'),
                'height': video_stream.get('height')
            }
            return metadata
    except ffmpeg.Error as e:
        print(f"FFmpeg error: {e.stderr.decode('utf8')}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
    return None

async def download_from_url(url):
    ydl_opts = {
        'outtmpl': os.path.join(Config.InDir, '%(title)s-%(id)s.%(ext)s'),
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)
            return filename
    except Exception as e:
        print(f"Error downloading from URL: {e}")
        return None


async def compress(event, video_data, input_path=None):
    msg: Message = event.message if not input_path else None
    chat_id = event.chat_id
    file_id = video_data.get("file_id")
    if not file_id:
        file_id = video_data.get("file_path")

    attributes = msg.media.document.attributes if msg and msg.media and hasattr(msg.media, "document") else []
    mime_type = msg.media.document.mime_type if msg and msg.media and hasattr(msg.media, "document") else "video/mp4" # Default mime type
    edit_message = await bot.send_message(chat_id, "Ꮲʀᴇᴘᴀʀᴀᴛɪᴏɴ Ꭲᴏ Ꮲʀᴏᴄᴇѕѕ", reply_to=msg.id if msg else None)

    if not os.path.isdir(Config.InDir):
        os.makedirs(Config.InDir, exist_ok=True)
    if not os.path.isdir(Config.OutDir):
        os.makedirs(Config.OutDir, exist_ok=True)

    if input_path:
        in_path = input_path
        file_name = os.path.basename(in_path)
    else:
        for attr in attributes:
            if isinstance(attr, DocumentAttributeFilename):
                file_name = attr.file_name
                break
        else:
            ext = mime_type.split("/")[1] if "/" in mime_type else "mp4"
            file_name = f"video.{ext}"
        in_path = os.path.join(Config.InDir, file_name)
        try:
            await fast_download(in_path, msg.media.document, bot, edit_message, time(), "Ꭰᴏᴡɴʟᴏᴀᴅɪɴɢ . . .")
        except Exception as e:
            print(e)
            return await edit_message.edit(f"💢 **Aɴ Eʀʀᴏʀ Oᴄᴄᴜʀᴇᴅ Wʜɪʟᴇ Dᴏᴡɴʟᴏᴀᴅɪɴɢ**", link_preview=False)

    out_path = os.path.join(Config.OutDir, f"compressed_{file_name}")

    FT = time()
    progress = f"progress-{FT}.txt"
    fps = f" -r {video_data.get('fps')}" if video_data.get('fps') else ""
    scale_option = ""
    if video_data.get('scale'):
        scale_option = f' -vf scale={video_data["scale"]}'

    crf = video_data.get('crf', db.crf) # Use stored crf or default
    speed = video_data.get('speed', db.speed) # Use stored speed or default

    cmd = (f'ffmpeg -hide_banner -loglevel quiet'
           f' -progress {progress} -i """{in_path}"""'
           f' -preset {speed} -vcodec libx265 -crf {crf}'
           f'{fps}{scale_option} -acodec copy -c:s copy """{out_path}""" -y')
    try:
        await ffmpeg_progress(cmd, in_path, progress, FT, edit_message)
    except Exception as e:
        print(e)
        return await edit_message.edit(f"💢***Aɴ Eʀʀᴏʀ Oᴄᴄᴜʀᴇᴅ Wʜɪʟᴇ FFMPEG Pʀᴏɢʀᴇѕѕ**", link_preview=False)

    in_size = humanbytes(os.path.getsize(in_path))
    out_size = humanbytes(os.path.getsize(out_path))
    text = f'Ᏼᴇғᴏʀᴇ Ꮯᴏᴍᴘʀᴇѕѕɪɴɢ: `{in_size}`\n\nᎪғᴛᴇʀ Ꮯᴏᴍᴘʀᴇѕѕɪɴɢ: `{out_size}`\n\nᏢᴏᴡᴇʀᴇᴅ Ᏼʏ  **@SA_SYR**'
    if db.original:
        thumb = await bot.download_media(msg, thumb=-1) if msg else Config.Thumb
    else:
        thumb = Config.Thumb
    try:
        uploader = await fast_upload(out_path, os.path.basename(out_path), time(), bot, edit_message, '**Uᴘʟᴏᴀᴅɪɴɢ**')
        if db.doc:
            await bot.send_file(chat_id, uploader, thumb=thumb, force_document=True)
        else:
            try:
                metadata = ethon_video_metadata(out_path)
                width = metadata["width"]
                height = metadata["height"]
                duration = metadata["duration"]
                attributes = [DocumentAttributeVideo(duration=duration, w=width, h=height, supports_streaming=True)]
                await bot.send_file(chat_id, uploader, thumb=thumb, attributes=attributes, supports_streaming=True)
            except Exception as e:
                print(e)
                await bot.send_file(chat_id, uploader, thumb=thumb, attributes=attributes, supports_streaming=True)
        await bot.send_message(chat_id, text)
    except Exception as e:
        print(e)
        return await edit_message.edit(f"💢 **Aɴ Eʀʀᴏʀ Oᴄᴄᴜʀᴇᴅ Wʜɪʟᴇ Uᴘʟᴏᴀᴅɪɴɢ**", link_preview=False)

    await edit_message.delete()
    if not input_path and os.path.exists(in_path):
        os.remove(in_path)
    if os.path.exists(out_path):
        os.remove(out_path)
    if os.path.exists(progress):
        os.remove(progress)


async def ffmpeg_progress(cmd, file, progress, now, event):
    total_frames = tf(file)
    with open(progress, "w"):
        pass
    proce = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    while proce.returncode is None:
        await asyncio.sleep(3)
        try:
            with open(progress, "r+") as fil:
                text = fil.read()
                frames = re.findall("frame=(\\d+)", text)
                size = re.findall("total_size=(\\d+)", text)
                speed = 0
                if len(frames):
                    elapse = int(frames[-1])
                if len(size):
                    size = int(size[-1])
                    per = elapse * 100 / int(total_frames) if total_frames > 0 and elapse > 0 else 0
                    time_diff = time() - int(now)
                    speed = round(elapse / time_diff, 2) if time_diff > 0 else 0
                if int(speed) != 0:
                    some_eta = int(((int(total_frames) - elapse) / speed) * 1000) if total_frames > elapse and speed > 0 else 0
                    progress_str = "**[{0}{1}]** `| {2}%\n\n`".format(
                        "".join("●" for _ in range(math.floor(per / 5))),
                        "".join("○" for _ in range(20 - math.floor(per / 5))),
                        round(per, 2),
                    )
                    e_size = humanbytes(size) + " ᴏғ " + humanbytes((size / per) * 100) if per > 0 else humanbytes(size) + " ᴏғ Unknown"
                    eta = time_formatter(some_eta)
                    await event.edit(f'🗜  Ꮯᴏᴍᴘʀᴇѕѕɪɴɢ ᎻᎬᏙᏟ\n\n{progress_str}' + f'**Pʀᴏɢʀᴇѕѕ**: {e_size}\n\n⏰ **Tɪᴍᴇ Lᴇғᴛ :** {eta}')
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error reading progress: {e}")
            break
    if proce.returncode != 0:
        stderr = await proce.stderr.read()
        print(f"FFmpeg error during processing: {stderr.decode()}")
        raise Exception("FFmpeg processing failed")


def time_formatter(milliseconds: int) -> str:
    """Inputs time in milliseconds, to get beautified time,
    as string"""
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    weeks, days = divmod(days, 7)
    tmp = (
        ((str(weeks) + "w:") if weeks else "")
        + ((str(days) + "d:") if days else "")
        + ((str(hours) + "h:") if hours else "")
        + ((str(minutes) + "m:") if minutes else "")
        + ((str(seconds) + "s:") if seconds else "")
    )
    if tmp.endswith(":"):
        return tmp[:-1]
    else:
        return tmp


def humanbytes(size):
    if size in [None, ""]:
        return "0 B"
    for unit in ["ʙ", "ᴋʙ", "ᴍʙ", "ɢʙ", "TB", "PB", "EB", "ZB", "YB"]:
        if size < 1024:
            break
        size /= 1024
    return f"{size:.2f} {unit}"
