from motor.motor_asyncio import AsyncIOMotorClient

from utils.get_project_settings import get_settings

settings = get_settings()

client = AsyncIOMotorClient(settings.MONGO_URI)
db = client[settings.MONGO_DB]
