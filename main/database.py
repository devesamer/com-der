
from motor.motor_asyncio import AsyncIOMotorClient
import aiofiles
import logging

from main.config import Config

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)


class Database:
    def __init__(self):
        self.mongo = AsyncIOMotorClient(Config.DB_URI)
        self.db = self.mongo[Config.DB_NAME]
        self.config = self.db["config2"]
        self.thumb = self.db["thumb"]
        self.doc = False
        self.speed = "ultrafast"
        self.crf = 28
        self.fps = None
        self.original = True
        self.tasks = 0

    async def init(self):
        try:
            config = await self.config.find_one({})
            if config is None:
                await self.config.insert_one({"doc": self.doc, "speed": self.speed, "crf": self.crf, "fps": self.fps})
            else:
                self.doc = config.get("doc", self.doc)
                self.speed = config.get("speed", self.speed)
                self.crf = config.get("crf", self.crf)
                self.fps = config.get("fps", self.fps)

            thumb = await self.thumb.find_one({})
            if thumb is None:
                await self.thumb.insert_one({"original": True, "bytes": None})
            elif not thumb["original"]:
                self.original = False
                thumb_bytes = thumb.get("bytes")
                if thumb_bytes:
                    async with aiofiles.open(Config.Thumb, "wb") as f:
                        await f.write(thumb_bytes)
                else:
                    logging.warning("Thumbnail bytes not found in database, using original.")
                    self.original = True
            else:
                self.original = True

        except Exception as e:
            logging.error(f"Error initializing database: {e}")

    async def set_speed(self, speed: str):
        try:
            self.speed = speed
            await self.config.update_one({}, {"$set": {"speed": speed}})
        except Exception as e:
            logging.error(f"Error setting speed in database: {e}")

    async def set_crf(self, crf: int):
        try:
            self.crf = crf
            await self.config.update_one({}, {"$set": {"crf": crf}})
        except Exception as e:
            logging.error(f"Error setting CRF in database: {e}")

    async def set_fps(self, fps: [int, None]):
        try:
            self.fps = fps
            await self.config.update_one({}, {"$set": {"fps": fps}})
        except Exception as e:
            logging.error(f"Error setting FPS in database: {e}")

    async def set_thumb(self, original=True):
        try:
            if original:
                await self.thumb.update_one({}, {"$set": {"original": True, "bytes": None}})
                self.original = True
            else:
                async with aiofiles.open(Config.Thumb, "rb") as f:
                    byt = await f.read()
                await self.thumb.update_one({}, {"$set": {"original": False, "bytes": byt}})
                self.original = False
        except Exception as e:
            logging.error(f"Error setting thumbnail in database: {e}")

    async def set_upload_mode(self, doc=False):
        try:
            self.doc = doc
            await self.config.update_one({}, {"$set": {"doc": doc}})
        except Exception as e:
            logging.error(f"Error setting upload mode in database: {e}")


db = Database()
