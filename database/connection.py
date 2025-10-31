from motor.motor_asyncio import AsyncIOMotorClient

import settings

client = AsyncIOMotorClient(settings.MONGO_URI)
db = client[settings.MONGO_DB]
