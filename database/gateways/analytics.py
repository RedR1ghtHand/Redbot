from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

import settings
from database.models import Session


class AnalyticsGateway:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.sessions_collection = db["sessions"]
        self.journal_collection = db["session_journal"]
        self.members_collection = db["members"]

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def _sessions_overlapping_reporting_range(range_start: datetime, range_end: datetime) -> dict:
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

    async def longest_sessions_all_time(self, limit: int = 10) -> list[Session]:
        cursor = self.sessions_collection.find({"duration": {"$ne": None}}).sort("duration", DESCENDING).limit(limit)
        return [Session(**doc) async for doc in cursor]

    async def longest_sessions_this_week(self, limit: int = 10) -> list[Session]:
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        cursor = self.sessions_collection.find(
            {
                "duration": {"$exists": True},
                "created_at": {"$gte": week_ago},
            }
        ).sort("duration", DESCENDING).limit(limit)
        return [Session(**doc) async for doc in cursor]

    async def get_stats_snapshot(
        self,
        lookback_days: int | None = None,
        top_limit: int = 10,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
    ) -> dict:
        if range_start is None or range_end is None:
            range_start, range_end = await self.get_reporting_range(lookback_days=lookback_days)

        range_start = self._ensure_utc(range_start)
        range_end = self._ensure_utc(range_end)
        query_strict = {"created_at": {"$gte": range_start, "$lte": range_end}}

        sessions = await self.sessions_collection.find(query_strict).to_list(length=None)
        sessions_for_journal = await self.sessions_collection.find(
            self._sessions_overlapping_reporting_range(range_start, range_end)
        ).to_list(length=None)
        session_ids = [
            session.get("channel_id") for session in sessions_for_journal if session.get("channel_id") is not None
        ]
        journal_query = {"session_id": {"$in": session_ids}} if session_ids else {"session_id": {"$in": []}}
        journals = await self.journal_collection.find(journal_query).to_list(length=None)
        members = await self.members_collection.find({}).to_list(length=None)

        sessions_by_channel = {
            session.get("channel_id"): session
            for session in sessions_for_journal
            if session.get("channel_id") is not None
        }
        member_name_by_id = {
            member.get("member_id"): member.get("public_name") or member.get("username") or "Unknown"
            for member in members
            if member.get("member_id") is not None
        }

        total_voice_seconds = int(sum(int(session.get("duration") or 0) for session in sessions))
        sessions_count = len(sessions)
        avg_session_seconds = int(total_voice_seconds / sessions_count) if sessions_count else 0

        participants_by_session: dict[int, set[int]] = {}
        participant_time: dict[int, int] = {}

        for entry in journals:
            session_id = entry.get("session_id")
            session = sessions_by_channel.get(session_id)
            if session is None:
                continue

            user_data = entry.get("user_joined") or {}
            participant_id = user_data.get("member_id")
            if participant_id is None:
                continue

            joined_at = entry.get("user_joined_at")
            left_at = entry.get("user_left_at")
            if joined_at is None:
                continue
            joined_at = self._ensure_utc(joined_at)
            if left_at is not None:
                left_at = self._ensure_utc(left_at)
            else:
                left_at = min(datetime.now(timezone.utc), range_end)
            overlap_start = max(joined_at, range_start)
            overlap_end = min(left_at, range_end)
            if overlap_start >= overlap_end:
                continue
            duration = int(max(0, (overlap_end - overlap_start).total_seconds()))
            participants_by_session.setdefault(session_id, set()).add(participant_id)
            participant_time[participant_id] = participant_time.get(participant_id, 0) + duration

        unique_participants = len({member_id for ids in participants_by_session.values() for member_id in ids})
        sessions_with_participants_count = len(participants_by_session)
        avg_participants_per_session = (
            sum(len(ids) for ids in participants_by_session.values()) / sessions_with_participants_count
            if sessions_with_participants_count
            else 0.0
        )

        creator_time: dict[int, int] = {}
        for session in sessions:
            creator_id = session.get("creator_id")
            if creator_id is None:
                continue
            creator_time[creator_id] = creator_time.get(creator_id, 0) + int(session.get("duration") or 0)

        top_creators = sorted(creator_time.items(), key=lambda item: item[1], reverse=True)[:top_limit]
        top_participants = sorted(participant_time.items(), key=lambda item: item[1], reverse=True)[:top_limit]

        combined_ids = set(participant_time) | set(creator_time)
        combined_rows: list[tuple[int, int, int, int]] = []
        for member_id in combined_ids:
            p_sec = participant_time.get(member_id, 0)
            c_sec = creator_time.get(member_id, 0)
            combined_rows.append((member_id, p_sec, c_sec, p_sec + c_sec))
        combined_rows.sort(key=lambda row: (-row[3], row[0]))
        leaderboard_top_combined = [
            {
                "member_id": member_id,
                "name": member_name_by_id.get(member_id, f"ID {member_id}"),
                "participant_seconds": p_sec,
                "creator_seconds": c_sec,
                "combined_seconds": p_sec + c_sec,
            }
            for member_id, p_sec, c_sec, _ in combined_rows[:top_limit]
        ]

        return {
            "total_voice_seconds": total_voice_seconds,
            "sessions_count": sessions_count,
            "avg_session_seconds": avg_session_seconds,
            "unique_participants": unique_participants,
            "avg_participants_per_session": avg_participants_per_session,
            "top_creators": [
                {
                    "member_id": member_id,
                    "name": member_name_by_id.get(member_id, f"ID {member_id}"),
                    "seconds": seconds,
                }
                for member_id, seconds in top_creators
            ],
            "top_participants": [
                {
                    "member_id": member_id,
                    "name": member_name_by_id.get(member_id, f"ID {member_id}"),
                    "seconds": seconds,
                }
                for member_id, seconds in top_participants
            ],
            "leaderboard_top_combined": leaderboard_top_combined,
        }

    async def get_reporting_range(self, lookback_days: int | None = None) -> tuple[datetime, datetime]:
        now = datetime.now(timezone.utc)
        if lookback_days is not None:
            return now - timedelta(days=lookback_days), now

        oldest_session = await self.sessions_collection.find_one(
            {"created_at": {"$exists": True}},
            sort=[("created_at", 1)],
        )
        if oldest_session and oldest_session.get("created_at"):
            started_at = self._ensure_utc(oldest_session["created_at"])
            return started_at, now
        return now, now

    async def get_journal_start_date(self) -> datetime | None:
        if settings.JOURNAL_METRICS_START_DATE is None:
            return None
        return self._ensure_utc(settings.JOURNAL_METRICS_START_DATE)

    async def get_detailed_metrics_range(self, lookback_days: int | None = None) -> tuple[datetime, datetime]:
        range_start, range_end = await self.get_reporting_range(lookback_days=lookback_days)
        journal_start = await self.get_journal_start_date()
        if journal_start is not None and journal_start > range_start:
            range_start = journal_start
        return range_start, range_end

    async def get_activity_by_hour(
        self,
        lookback_days: int | None = None,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
    ) -> list[dict]:
        if range_start is None or range_end is None:
            range_start, range_end = await self.get_reporting_range(lookback_days=lookback_days)

        range_start = self._ensure_utc(range_start)
        range_end = self._ensure_utc(range_end)

        tz = settings.get_reporting_timezone()

        journals = await self.journal_collection.find({}).to_list(length=None)
        entries: list[tuple[int, datetime, datetime]] = []

        for entry in journals:
            joined_at = entry.get("user_joined_at")
            left_at = entry.get("user_left_at") or range_end
            user_data = entry.get("user_joined") or {}
            participant_id = user_data.get("member_id")

            if joined_at is None or participant_id is None:
                continue
            joined_at = self._ensure_utc(joined_at)
            left_at = self._ensure_utc(left_at)
            if joined_at > range_end or left_at < range_start:
                continue

            start = max(joined_at, range_start)
            end = min(range_end, max(start, left_at))
            entries.append((participant_id, start, end))

        samples_count = {hour: 0 for hour in range(24)}
        active_sum = {hour: 0 for hour in range(24)}

        range_start_local = range_start.astimezone(tz)
        cursor_local = range_start_local.replace(minute=0, second=0, microsecond=0)

        while True:
            slot_start_local = cursor_local
            slot_end_local = cursor_local + timedelta(hours=1)
            slot_start_utc = slot_start_local.astimezone(timezone.utc)
            if slot_start_utc >= range_end:
                break

            slot_end_utc = slot_end_local.astimezone(timezone.utc)
            seg_start = max(slot_start_utc, range_start)
            seg_end = min(slot_end_utc, range_end)

            if seg_start < seg_end:
                active: set[int] = set()
                for participant_id, ja, la in entries:
                    overlap_start = max(ja, seg_start)
                    overlap_end = min(la, seg_end)
                    if overlap_start < overlap_end:
                        active.add(participant_id)

                hour_of_day = slot_start_local.hour
                active_sum[hour_of_day] += len(active)
                samples_count[hour_of_day] += 1

            cursor_local += timedelta(hours=1)

        return [
            {
                "hour": hour,
                "avg_active_participants": (
                    active_sum[hour] / samples_count[hour] if samples_count[hour] else 0.0
                ),
            }
            for hour in range(24)
        ]

    async def get_weekday_voice_trends(
        self,
        lookback_days: int | None = None,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        if range_start is None or range_end is None:
            range_start, range_end = await self.get_reporting_range(lookback_days=lookback_days)

        range_start = self._ensure_utc(range_start)
        range_end = self._ensure_utc(range_end)
        range_query = {"created_at": {"$gte": range_start, "$lte": range_end}}

        sessions = await self.sessions_collection.find(range_query).to_list(length=None)
        session_ids = [session.get("channel_id") for session in sessions if session.get("channel_id") is not None]
        journal_query = {"session_id": {"$in": session_ids}} if session_ids else {"session_id": {"$in": []}}
        journals = await self.journal_collection.find(journal_query).to_list(length=None)

        sessions_by_id = {
            session["channel_id"]: session for session in sessions if session.get("channel_id") is not None
        }
        session_participant_seconds: dict[int, int] = {}
        session_participants: dict[int, set[int]] = {}

        for entry in journals:
            session_id = entry.get("session_id")
            if session_id not in sessions_by_id:
                continue
            user_data = entry.get("user_joined") or {}
            participant_id = user_data.get("member_id")
            if participant_id is None:
                continue
            joined_at = entry.get("user_joined_at")
            left_at = entry.get("user_left_at")
            duration = int(max(0, (left_at - joined_at).total_seconds())) if joined_at and left_at else 0
            session_participant_seconds[session_id] = session_participant_seconds.get(session_id, 0) + duration
            session_participants.setdefault(session_id, set()).add(participant_id)

        daily_metrics: dict[datetime.date, dict] = {}
        for session_id, session in sessions_by_id.items():
            created_at = session.get("created_at")
            if created_at is None:
                continue
            created_at = self._ensure_utc(created_at)
            if created_at < range_start or created_at > range_end:
                continue
            day_key = created_at.date()
            day_data = daily_metrics.setdefault(
                day_key,
                {
                    "total_participant_seconds": 0,
                    "total_participants": 0,
                    "sessions_count": 0,
                },
            )
            participants_count = len(session_participants.get(session_id, set()))
            participant_seconds = session_participant_seconds.get(session_id, 0)
            day_data["total_participant_seconds"] += participant_seconds
            day_data["total_participants"] += participants_count
            day_data["sessions_count"] += 1

        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday_points: list[dict] = []

        if lookback_days == 7:
            week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            for weekday_index, weekday_name in enumerate(weekday_names):
                day = (week_start + timedelta(days=weekday_index)).date()
                day_data = daily_metrics.get(
                    day, {"total_participant_seconds": 0, "total_participants": 0, "sessions_count": 0}
                )
                sessions_count = day_data["sessions_count"]
                total_participant_seconds = day_data["total_participant_seconds"]
                total_participants = day_data["total_participants"]
                avg_voice_time = total_participant_seconds / sessions_count if sessions_count else 0.0
                avg_users = total_participants / sessions_count if sessions_count else 0.0
                avg_time_per_user = total_participant_seconds / total_participants if total_participants else 0.0
                weekday_points.append(
                    {
                        "weekday": weekday_name,
                        "avg_voice_time_hours": avg_voice_time / 3600,
                        "avg_users_participated": avg_users,
                        "avg_time_per_user_hours": avg_time_per_user / 3600,
                    }
                )
            mode = "this_week"
        else:
            cursor_day = range_start.date()
            end_day = range_end.date()
            bucketed: dict[int, list[dict]] = {idx: [] for idx in range(7)}
            while cursor_day <= end_day:
                day_data = daily_metrics.get(
                    cursor_day, {"total_participant_seconds": 0, "total_participants": 0, "sessions_count": 0}
                )
                sessions_count = day_data["sessions_count"]
                total_participant_seconds = day_data["total_participant_seconds"]
                total_participants = day_data["total_participants"]
                bucketed[cursor_day.weekday()].append(
                    {
                        "avg_voice_time_hours": (
                            (total_participant_seconds / sessions_count) / 3600 if sessions_count else 0.0
                        ),
                        "avg_users_participated": (total_participants / sessions_count if sessions_count else 0.0),
                        "avg_time_per_user_hours": (
                            (total_participant_seconds / total_participants) / 3600 if total_participants else 0.0
                        ),
                    }
                )
                cursor_day += timedelta(days=1)

            for weekday_index, weekday_name in enumerate(weekday_names):
                rows = bucketed[weekday_index]
                count = len(rows)
                if count == 0:
                    weekday_points.append(
                        {
                            "weekday": weekday_name,
                            "avg_voice_time_hours": 0.0,
                            "avg_users_participated": 0.0,
                            "avg_time_per_user_hours": 0.0,
                        }
                    )
                    continue
                weekday_points.append(
                    {
                        "weekday": weekday_name,
                        "avg_voice_time_hours": sum(row["avg_voice_time_hours"] for row in rows) / count,
                        "avg_users_participated": sum(row["avg_users_participated"] for row in rows) / count,
                        "avg_time_per_user_hours": sum(row["avg_time_per_user_hours"] for row in rows) / count,
                    }
                )
            mode = "weekday_average"

        summary = {
            "avg_voice_time_seconds": (
                sum(point["avg_voice_time_hours"] for point in weekday_points) / 7
            ) * 3600,
            "avg_users_participated": sum(point["avg_users_participated"] for point in weekday_points) / 7,
            "avg_time_per_user_seconds": (
                sum(point["avg_time_per_user_hours"] for point in weekday_points) / 7
            ) * 3600,
        }
        return {"mode": mode, "points": weekday_points, "summary": summary}
