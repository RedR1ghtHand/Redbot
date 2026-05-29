from datetime import datetime, timedelta

from database.repositories import StatsReadRepository


class WeekdayTrendsCalculator:
    def __init__(self, stats_read_repository: StatsReadRepository):
        self.stats_read_repository = stats_read_repository

    async def compute(
        self,
        range_start: datetime,
        range_end: datetime,
    ) -> dict:
        range_start = self.stats_read_repository.ensure_utc(range_start)
        range_end = self.stats_read_repository.ensure_utc(range_end)

        sessions = await self.stats_read_repository.get_sessions_in_range(range_start, range_end)
        session_ids = [session.get("channel_id") for session in sessions if session.get("channel_id") is not None]
        journals = await self.stats_read_repository.get_journals_by_session_ids(session_ids)

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
            created_at = self.stats_read_repository.ensure_utc(created_at)
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
