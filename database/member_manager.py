from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models import Member


class MemberManager:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["members"]

    async def upsert_member(
        self,
        member_id: int,
        username: str,
        public_name: str,
        avatar_url: str,
        is_admin: bool = False,
    ) -> Member:
        payload = {
            "member_id": member_id,
            "username": username,
            "public_name": public_name,
            "avatar_url": avatar_url,
            "is_admin": is_admin,
        }
        await self.collection.update_one(
            {"member_id": member_id},
            {"$set": payload},
            upsert=True,
        )
        return Member(**payload)

    async def get_member(self, member_id: int) -> Member | None:
        member_data = await self.collection.find_one({"member_id": member_id})
        return Member(**member_data) if member_data else None

    async def get_members_map(self, member_ids: list[int]) -> dict[int, Member]:
        ids = list({member_id for member_id in member_ids if member_id is not None})
        if not ids:
            return {}

        cursor = self.collection.find({"member_id": {"$in": ids}})
        members = [Member(**doc) async for doc in cursor]
        return {member.member_id: member for member in members}
