# main/utils.py
from time import time
import asyncio
import math
import os
import re
import ffmpeg

from telethon import Button, events
from telethon.events import CallbackQuery
from telethon.tl.types import Message, DocumentAttributeFilename, DocumentAttributeVideo
from ethon.telefunc import fast_download, fast_upload
from ethon.pyfunc import video_metadata as get_metadata, total_frames as tf

from main.client import bot
from main.config import Config
from main.database import db


async def get_video_info(video_document, client, is_file_path=False):
    try:
        if is_file_path:
            metadata = get_metadata(video_document)
            codec_streams = metadata.get('streams', [])
            video_stream = next((s for s in codec_streams if s.get('codec_type') == 'video'), None)
            codec = video_stream.get('codec_name') if video_stream else None
            width = metadata.get('width')
            height = metadata.get('height')
            return {'codec': codec, 'width': width, 'height': height}
        else:
            file_path = os.path.join(Config.InDir, f"temp_video_{time()}")
            await fast_download(file_path, video_document, client, progress_callback=None)
            metadata = get_metadata(file_path)
            codec_streams = metadata.get('streams', [])
            video_stream = next((s for s in codec_streams if s.get('codec_type') == 'video'), None)
            codec = video_stream.get('codec_name') if video_stream else None
            width = metadata.get('width')
            height = metadata.get('height')
            os.remove(file_path)
            return {'codec': codec, 'width': width, 'height': height}
    except Exception as e:
        print(f"Error getting video info: {e}")
        return None


async def compress(event, video_document=None, file_path=None, speed="ultrafast", crf=28, fps=None, resolution="original", width=None, height=None):
    msg: Message = event.message
    edit = await bot.send_message(event.chat_id, "Ꮲʀᴇᴘᴀʀᴀᴛɪᴏɴ Ꭲᴏ Ꮲʀᴏᴄᴇѕѕ", reply_to=msg.id if msg else None)

    if not os.path.isdir(Config.InDir):
        os.makedirs(Config.InDir, exist_ok=True)
    if not os.path.isdir(Config.OutDir):
        os.makedirs(Config.OutDir, exist_ok=True)

    if video_document:
        attributes = video_document.attributes
        mime_type = video_document.mime_type
        for attr in attributes:
            if isinstance(attr, DocumentAttributeFilename):
                file_name = attr.file_name
                break
        else:
            ext = mime_type.split("/")[1]
            file_name = f"video.{ext}"
        in_path = os.path.join(Config.InDir, file_name)
        try:
            await fast_download(in_path, video_document, bot, edit, time(), "Ꭰᴏᴡɴʟᴏᴀᴅɪɴɢ . . .")
        except Exception as e:
            print(e)
            return await edit.edit(f"💢 **Aɴ Eʀʀᴏʀ Oᴄᴄᴜʀᴇᴅ Wʜɪʟᴇ Dᴏᴡɴʟᴏᴀᴅɪɴɢ**", link_preview=False)
    elif file_path:
        in_path = file_path
        file_name = os.path.basename(file_path)
    else:
        return await edit.edit("⚠️ Input video source not found.")

    out_path = os.path.join(Config.OutDir, f"compressed_{file_name}")

    fps_option = f" -r {fps}" if fps else ""
    scale_option = ""
    if width is not None and height is not None:
        scale_option = f' -vf scale={width}:{height}'
    elif resolution != "original":
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

    FT = time()
    progress = f"progress-{FT}.txt"
    cmd = (f'ffmpeg -hide_banner -loglevel quiet'
           f' -progress {progress} -i """{in_path}"""'
           f' -preset {speed} -vcodec libx265 -crf {crf}'
           f'{fps_option}{scale_option} -acodec copy -c:s copy """{out_path}""" -y')
    try:
        await ffmpeg_progress(cmd, in_path, progress, FT, edit)
    except Exception as e:
        print(e)
        return await edit.edit(f"💢***Aɴ Eʀʀᴏʀ Oᴄᴄᴜʀᴇᴅ Wʜɪʟᴇ FFMPEG Pʀᴏɢʀᴇѕѕ**", link_preview=False)

    in_size = humanbytes(os.path.getsize(in_path))
    out_size = humanbytes(os.path.getsize(out_path))
    text = f'Ᏼᴇғᴏʀᴇ Ꮯᴏᴍᴘʀᴇѕѕɪɴɢ: `{in_size}`\n\nᎪғᴛᴇʀ Ꮯᴏᴍᴘʀᴇѕѕɪɴɢ: `{out_size}`\n\nᏢᴏᴡᴇʀᴇᴅ Ᏼʏ  **@SA_SYR**'
    if db.original and video_document:
        thumb = await bot.download_media(msg, thumb=-1)
    else:
        thumb = Config.Thumb
    try:
        uploader = await fast_upload(out_path, os.path.basename(out_path), time(), bot, edit, '**Uᴘʟᴏᴀᴅɪɴɢ**')
        if db.doc:
            await bot.send_file(event.chat_id, uploader, thumb=thumb, force_document=True)
        else:
            try:
                metadata = get_metadata(out_path)
                width = metadata["width"]
                height = metadata["height"]
                duration = metadata["duration"]
                attributes = [DocumentAttributeVideo(duration=duration, w=width, h=height, supports_streaming=True)]
                await bot.send_file(event.chat_id, uploader, thumb=thumb, attributes=attributes, supports_streaming=True)
            except Exception as e:
                print(e)
                await bot.send_file(event.chat_id, uploader, thumb=thumb, attributes=attributes, supports_streaming=True)
        await bot.send_message(event.chat_id, text)
    except Exception as e:
        print(e)
        return await edit.edit(f"💢 **Aɴ Eʀʀᴏʀ Oᴄᴄᴜʀᴇᴅ Wʜɪʟᴇ Uᴘʟᴏᴀᴅɪɴɢ**", link_preview=False)

    await edit.delete()
    if video_document and os.path.exists(in_path):
        os.remove(in_path)
    if os.path.exists(out_path):
        os.remove(out_path)


async def ffmpeg_progress(cmd, file, progress, now, event):
    try:
        total_frames = tf(file)
    except Exception as e:
        print(f"Error getting total frames: {e}")
        total_frames = None

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
                    if total_frames:
                        per = elapse * 100 / int(total_frames)
                        time_diff = time() - int(now)
                        speed = round(elapse / time_diff, 2)
                    else:
                        per = 0
                if int(speed) != 0 and total_frames:
                    some_eta = int(((int(total_frames) - elapse) / speed) * 1000)
                    progress_str = "**[{0}{1}]** `| {2}%\n\n`".format(
                        "".join("●" for _ in range(math.floor(per / 5))),
                        "".join("○" for _ in range(20 - math.floor(per / 5))),
                        round(per, 2),
                    )
                    e_size = humanbytes(size) + " ᴏғ " + (humanbytes((size / per) * 100) if per > 0 else "N/A")
                    eta = time_formatter(some_eta)
                    await event.edit(f'🗜  Ꮯᴏᴍᴘʀᴇѕѕɪɴɢ ᎻᎬᏙᏟ\n\n{progress_str}' + f'**Pʀᴏɢʀᴇѕѕ**: {e_size}\n\n⏰ **Tɪᴍᴇ Lᴇғᴛ :** {eta}')
                elif total_frames is None and len(size):
                    e_size = humanbytes(size)
                    await event.edit(f'🗜  Ꮯᴏᴍᴘʀᴇѕѕɪɴɢ ᎻᎬᏙᏟ\n\n**Pʀᴏɢʀᴇѕѕ**: {e_size}')
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error in progress update: {e}")
            pass
    if proce.returncode != 0:
        stderr = await proce.stderr.read()
        print(f"FFmpeg Error: {stderr.decode()}")
        raise Exception("FFmpeg processing failed")


def time_formatter(milliseconds: int) -> str:
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

