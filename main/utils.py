
from time import time
import asyncio
import math
import os
import re
import ffmpeg
import logging

from telethon import Button, events
from telethon.events import CallbackQuery
from telethon.tl.types import Message, DocumentAttributeFilename, DocumentAttributeVideo
from ethon.telefunc import fast_download, fast_upload
from ethon.pyfunc import video_metadata, total_frames as tf

from main.client import bot
from main.config import Config
from main.database import db

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)


async def compress(event: events.CallbackQuery.Event, speed: str, resolution: str, fps: [int, str, None], crf: int):
    msg: Message = await bot.get_messages(event.chat_id, ids=int(event.pattern_match.group(1)))
    if not msg or not msg.media or not hasattr(msg.media, "document"):
        await event.respond("Error: Original video not found.")
        return

    attributes = msg.media.document.attributes
    mime_type = msg.media.document.mime_type
    edit = await bot.send_message(event.chat_id, "⚙️ Preparing to process...", reply_to=msg.id)

    for attr in attributes:
        if isinstance(attr, DocumentAttributeFilename):
            file_name = attr.file_name
            break
    else:
        ext = mime_type.split("/")[1]
        file_name = f"video.{ext}"

    if not os.path.isdir(Config.InDir):
        os.makedirs(Config.InDir, exist_ok=True)
    in_path = os.path.join(Config.InDir, file_name)

    try:
        await fast_download(in_path, msg.media.document, bot, edit, time(), "📥 Downloading...")
    except Exception as e:
        logging.error(f"Error during download: {e}")
        return await edit.edit(f"💢 **Error during download:** {e}", link_preview=False)

    if not os.path.isdir(Config.OutDir):
        os.makedirs(Config.OutDir, exist_ok=True)
    out_path = os.path.join(Config.OutDir, f"compressed_{file_name}")

    FT = time()
    progress = f"progress-{FT}.txt"
    fps_arg = f" -r {fps}" if fps and fps != "original" else ""
    scale_option = ""

    if resolution:
        width, height = None, None
        if resolution == '240p':
            width, height = 426, 240
        elif resolution == '360p':
            width, height = 640, 360
        elif resolution == '480p':
            width, height = 854, 480
        elif resolution == '720p':
            width, height = 1280, 720
        elif resolution == '1080p':
            width, height = 1920, 1080
        if width and height:
            scale_option = f' -vf scale={width}:{height}'

    cmd = (f'ffmpeg -hide_banner -loglevel quiet'
           f' -progress {progress} -i """{in_path}"""'
           f' -preset {speed} -vcodec libx265 -crf {crf}'
           f'{fps_arg}{scale_option} -acodec copy -c:s copy """{out_path}""" -y')
    try:
        await ffmpeg_progress(cmd, in_path, progress, FT, edit)
    except Exception as e:
        logging.error(f"FFmpeg error: {e}")
        return await edit.edit(f"💢 **Error during compression:** {e}", link_preview=False)

    in_size = humanbytes(os.path.getsize(in_path))
    out_size = humanbytes(os.path.getsize(out_path))
    text = f'📊 **Compression Report:**\n\nBefore: `{in_size}`\nAfter: `{out_size}`\n\nPowered by @SA_SYR'
    if db.original:
        thumb = await bot.download_media(msg, thumb=-1)
    else:
        thumb = Config.Thumb
    try:
        await edit.edit("📤 Uploading...")
        uploader = await fast_upload(out_path, f"compressed_{file_name}", time(), bot, edit, '**Uploading** ⬆️')
        if db.doc:
            await bot.send_file(event.chat_id, uploader, thumb=thumb, force_document=True)
        else:
            try:
                metadata = video_metadata(out_path)
                width = metadata.get("width")
                height = metadata.get("height")
                duration = metadata.get("duration")
                attributes = [DocumentAttributeVideo(duration=duration, w=width, h=height, supports_streaming=True)] if duration and width and height else []
                await bot.send_file(event.chat_id, uploader, thumb=thumb, attributes=attributes, supports_streaming=True)
            except Exception as e:
                logging.warning(f"Error getting video metadata: {e}")
                await bot.send_file(event.chat_id, uploader, thumb=thumb, supports_streaming=True)
        await bot.send_message(event.chat_id, text)
    except Exception as e:
        logging.error(f"Error during upload: {e}")
        return await edit.edit(f"💢 **Error during upload:** {e}", link_preview=False)
    finally:
        try:
            await edit.delete()
        except Exception as e:
            logging.warning(f"Error deleting progress message: {e}")
        try:
            os.remove(in_path)
            os.remove(out_path)
            if os.path.exists(progress):
                os.remove(progress)
        except Exception as e:
            logging.warning(f"Error cleaning up files: {e}")


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
                if frames:
                    elapse = int(frames[-1])
                else:
                    elapse = 0
                if size:
                    size = int(size[-1])
                    if total_frames > 0:
                        per = elapse * 100 / int(total_frames)
                        time_diff = time() - int(now)
                        speed = round(elapse / time_diff, 2) if time_diff > 0 else 0
                    else:
                        per = 0
                else:
                    per = 0

                if speed > 0:
                    some_eta = int(((int(total_frames) - elapse) / speed) * 1000) if total_frames > elapse else 0
                    progress_str = "**[{0}{1}]** `| {2:.2f}%\n\n`".format(
                        "".join("●" for _ in range(math.floor(per / 5))),
                        "".join("○" for _ in range(20 - math.floor(per / 5))),
                        per,
                    )
                    e_size = humanbytes(size) + " of " + humanbytes((size / per) * 100 if per > 0 else 0)
                    eta = time_formatter(some_eta)
                    await event.edit(f'🗜️ Compressing...\n\n{progress_str}' + f'**Progress**: {e_size}\n\n⏳ **Time Left**: {eta}')
                else:
                    await event.edit(f'🗜️ Compressing...\n\n**Progress**: {humanbytes(size)}')
        except FileNotFoundError:
            pass
        except Exception as e:
            logging.warning(f"Error reading progress: {e}")
            break
    if proce.returncode != 0:
        stderr = await proce.stderr.read()
        logging.error(f"FFmpeg command failed with exit code {proce.returncode}: {stderr.decode()}")
        raise Exception(f"FFmpeg failed with code {proce.returncode}: {stderr.decode()}")


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
    return tmp[:-1] if tmp.endswith(":") else tmp


def humanbytes(size):
    if size in [None, ""]:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]:
        if size < 1024:
            break
        size /= 1024
    return f"{size:.2f} {unit}"
