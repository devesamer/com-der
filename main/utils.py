# main/utils.py
import os
import subprocess
import asyncio
from time import time
from main.config import Config
from main.__main__ import compression_tasks  # استيراد قاموس مهام الضغط

async def fast_download(file_path, video_document, client, progress_callback=None):
    async for chunk in client.iter_download(video_document):
        with open(file_path, 'ab') as f:
            f.write(chunk)
        if progress_callback:
            progress_callback()

def get_metadata(file_path):
    try:
        from ethon import pyfunc
        metadata = pyfunc.video_metadata(file_path)
        return metadata
    except Exception as e:
        print(f"Error getting metadata: {e}")
        return {}

async def get_video_info(video_document, client, is_file_path=False):
    try:
        if is_file_path:
            metadata = get_metadata(video_document)
            codec = metadata.get('codec')
            width = metadata.get('width')
            height = metadata.get('height')
            return {'codec': codec, 'width': width, 'height': height}
        else:
            file_path = os.path.join(Config.InDir, f"temp_video_{time()}")
            await fast_download(file_path, video_document, client, progress_callback=None)
            metadata = get_metadata(file_path)
            os.remove(file_path)
            codec = metadata.get('codec')
            width = metadata.get('width')
            height = metadata.get('height')
            return {'codec': codec, 'width': width, 'height': height}
    except Exception as e:
        print(f"Error getting video info: {e}")
        return None

async def compress(event, video_document=None, file_path=None, task_id=None, **kwargs):
    output_file = os.path.join(Config.OutDir, f"compressed_{time()}.mp4")
    temp_files_to_delete = [output_file]
    input_file = None

    try:
        if file_path:
            input_file = file_path
        elif video_document:
            input_file = os.path.join(Config.InDir, f"temp_input_{time()}")
            temp_files_to_delete.append(input_file)
            await fast_download(input_file, video_document, event._client)

        if not input_file:
            print("No input file provided for compression.")
            return

        command = [
            "ffmpeg",
            "-i", input_file,
            "-preset", kwargs.get('speed', 'medium'),
            "-c:v", "libx264",
            "-crf", str(kwargs.get('crf', 23)),
            "-c:a", "aac",
            "-strict", "-2"
        ]

        resolution = kwargs.get('resolution')
        width = kwargs.get('width')
        height = kwargs.get('height')

        if resolution and resolution != 'original':
            if resolution != 'custom':
                command.extend(["-vf", f"scale=-2:{resolution[:-1]}"])
            elif width and height:
                command.extend(["-vf", f"scale={width}:{height}"])

        fps = kwargs.get('fps')
        if fps:
            command.extend(["-r", str(fps)])

        command.append(output_file)

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        while process.returncode is None:
            await asyncio.sleep(1)
            if task_id in compression_tasks and compression_tasks[task_id]["status"] == "cancelled":
                try:
                    process.terminate()
                except OSError:
                    process.kill()
                break

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            await event.reply(file=output_file, force_document=await db.get_upload_mode())
        else:
            error = stderr.decode()
            print(f"FFmpeg Error: {error}")
            await event.reply(f"⚠️ Compression failed:\n`{error}`")

    except Exception as e:
        print(f"Compression error: {e}")
        await event.reply(f"⚠️ An error occurred during compression: `{e}`")

    finally:
        if task_id in compression_tasks and compression_tasks[task_id]["status"] == "cancelled":
            for temp_file in temp_files_to_delete:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        else:
            for temp_file in temp_files_to_delete:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
