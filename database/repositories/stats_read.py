from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

import settings
from database.models import Session


class StatsReadRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.sessions_collection = db["sessions"]
        self.journal_collection = db["session_journal"]
        self.members_collection = db["members"]

    @staticmethod
    def ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def sessions_overlapping_reporting_range(range_start: datetime, range_end: datetime) -> dict:
        return {
            "$and": [
                {"created_at": {"$lte": range_end}},
                {
                    "$or": [
                        {"is_ended": False},
                        {"updated_at": {"$gte": range_start}},
                        {"created_at": {"$gte": range_start}},
                    ]
                },
            ]
        }

    @staticmethod
    def journals_overlapping_reporting_range(range_start: datetime, range_end: datetime) -> dict:
        return {
            "$and": [
                {"user_joined_at": {"$lte": range_end}},
                {
                    "$or": [
                        {"user_left_at": None},
                        {"user_left_at": {"$gte": range_start}},
                    ]
                },
            ]
        }

    async def longest_sessions_all_time(self, limit: int = 10) -> list[Session]:
        cursor = self.sessions_collection.find({"duration": {"$ne": None}}).sort("duration", DESCENDING).limit(limit)
        return [Session(**doc) async for doc in cursor]

    async def get_reporting_range(self, lookback_days: int | None = None) -> tuple[datetime, datetime]:
        now = datetime.now(timezone.utc)
        if lookback_days is not None:
            return now - timedelta(days=lookback_days), now

        oldest_session = await self.sessions_collection.find_one(
            {"created_at": {"$exists": True}},
            sort=[("created_at", 1)],
        )
        if oldest_session and oldest_session.get("created_at"):
            started_at = self.ensure_utc(oldest_session["created_at"])
            return started_at, now
        return now, now

    async def get_journal_start_date(self) -> datetime | None:
        if settings.JOURNAL_METRICS_START_DATE is None:
            return None
        return self.ensure_utc(settings.JOURNAL_METRICS_START_DATE)

    async def get_detailed_stats_range(self, lookback_days: int | None = None) -> tuple[datetime, datetime]:
        range_start, range_end = await self.get_reporting_range(lookback_days=lookback_days)
        journal_start = await self.get_journal_start_date()
        if journal_start is not None and journal_start > range_start:
            range_start = journal_start
        return range_start, range_end

    async def get_sessions_in_range(self, range_start: datetime, range_end: datetime) -> list[dict]:
        query = {"created_at": {"$gte": range_start, "$lte": range_end}}
        return await self.sessions_collection.find(query).to_list(length=None)

    async def get_sessions_overlapping_range(self, range_start: datetime, range_end: datetime) -> list[dict]:
        query = self.sessions_overlapping_reporting_range(range_start, range_end)
        return await self.sessions_collection.find(query).to_list(length=None)

    async def get_journals_overlapping_range(self, range_start: datetime, range_end: datetime) -> list[dict]:
        query = self.journals_overlapping_reporting_range(range_start, range_end)
        return await self.journal_collection.find(query).to_list(length=None)

    async def get_journals_by_session_ids(self, session_ids: list[int]) -> list[dict]:
        if not session_ids:
            return []
        query = {"session_id": {"$in": session_ids}}
        return await self.journal_collection.find(query).to_list(length=None)

    async def get_all_journals(self) -> list[dict]:
        return await self.journal_collection.find({}).to_list(length=None)

    async def get_all_members(self) -> list[dict]:
        return await self.members_collection.find({}).to_list(length=None)
