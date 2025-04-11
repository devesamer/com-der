from motor.motor_asyncio import AsyncIOMotorClient
import aiofiles

from main.config import Config


class Database:
    def __init__(self):
        self.mongo = AsyncIOMotorClient(Config.DB_URI)
        self.db = self.mongo[Config.DB_NAME]
        self.config = self.db["config2"]
        self.thumb = self.db["thumb"]
        self.video_data = self.db["video_data"] # New collection for video specific data
        self.doc = False
        self.speed = "ultrafast"
        self.crf = 28
        self.fps = None
        self.original = True
        self.tasks = 0

    async def init(self):
        config = await self.config.find_one({})
        if config is None:
            await self.config.insert_one({"doc": self.doc, "speed": self.speed, "crf": self.crf, "fps": self.fps})
        else:
            self.doc = config["doc"]
            self.speed = config["speed"]
            self.crf = config["crf"]
            self.fps = config["fps"]
        thumb = await self.thumb.find_one({})
        if thumb is None:
            await self.thumb.insert_one({"original": True, "bytes": None})
        elif not thumb["original"]:
            self.original = False
            async with aiofiles.open(Config.Thumb, "wb") as f:
                await f.write(thumb["bytes"])

    async def set_speed(self, speed: str):
        self.speed = speed
        await self.config.update_one({}, {"$set": {"speed": speed}})

    async def set_crf(self, crf: int):
        self.crf = crf
        await self.config.update_one({}, {"$set": {"crf": crf}})

    async def set_fps(self, fps: [int, None]):
        self.fps = fps
        await self.config.update_one({}, {"$set": {"fps": fps}})

    async def set_thumb(self, original=True):
        if original:
            await self.thumb.update_one({}, {"$set": {"original": True}})
        else:
            async with aiofiles.open(Config.Thumb, "rb") as f:
                byt = await f.read()
            await self.thumb.update_one({}, {"$set": {"original": False, "bytes": byt}})
        self.original = original

    async def set_upload_mode(self, doc=False):
        self.doc = doc
        await self.config.update_one({}, {"$set": {"doc": doc}})

    async def set_video_data(self, chat_id, file_id, data: dict):
        await self.video_data.update_one({"chat_id": chat_id, "file_id": file_id}, {"$set": {"chat_id": chat_id, "file_id": file_id, **data}}, upsert=True)

    async def get_video_data(self, chat_id, file_id):
        result = await self.video_data.find_one({"chat_id": chat_id, "file_id": file_id})
        return result

    async def update_video_data(self, chat_id, file_id, data: dict):
        await self.video_data.update_one({"chat_id": chat_id, "file_id": file_id}, {"$set": data})

    async def clear_video_data(self, chat_id, file_id):
        await self.video_data.delete_one({"chat_id": chat_id, "file_id": file_id})

    async def set_temp_file(self, chat_id, file_path):
        await self.video_data.update_one({"chat_id": chat_id, "temp_file_key": True}, {"$set": {"chat_id": chat_id, "temp_file_key": True, "file_path": file_path}}, upsert=True)

    async def get_temp_file(self, chat_id):
        result = await self.video_data.find_one({"chat_id": chat_id, "temp_file_key": True})
        return result.get("file_path") if result else None

db = Database()
