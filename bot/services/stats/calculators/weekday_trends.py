from datetime import date, datetime, timedelta

import settings
from database.repositories import StatsReadRepository

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


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
        tz = settings.get_reporting_timezone()

        journals = await self.stats_read_repository.get_journals_overlapping_range(range_start, range_end)
        day_participants: dict[date, set[int]] = {}
        day_seconds: dict[date, float] = {}

        for entry in journals:
            joined_at = entry.get("user_joined_at")
            left_at = entry.get("user_left_at")
            user_data = entry.get("user_joined") or {}
            participant_id = user_data.get("member_id")
            if joined_at is None or left_at is None or participant_id is None:
                continue

            joined_at = self.stats_read_repository.ensure_utc(joined_at)
            left_at = self.stats_read_repository.ensure_utc(left_at)
            if joined_at > range_end or left_at < range_start:
                continue

            start = max(joined_at, range_start)
            end = min(range_end, max(start, left_at))
            self._accumulate_by_local_day(start, end, tz, participant_id, day_participants, day_seconds)

        active_by_weekday: dict[int, list[float]] = {idx: [] for idx in range(7)}
        time_per_user_by_weekday: dict[int, list[float]] = {idx: [] for idx in range(7)}

        cursor_day = range_start.astimezone(tz).date()
        end_day = range_end.astimezone(tz).date()
        while cursor_day <= end_day:
            weekday_index = cursor_day.weekday()
            participants = day_participants.get(cursor_day)
            active_count = len(participants) if participants else 0
            active_by_weekday[weekday_index].append(float(active_count))
            if active_count > 0:
                total_seconds = day_seconds.get(cursor_day, 0.0)
                time_per_user_by_weekday[weekday_index].append((total_seconds / active_count) / 3600.0)
            cursor_day += timedelta(days=1)

        weekday_points: list[dict] = []
        for weekday_index, weekday_name in enumerate(WEEKDAY_NAMES):
            active_values = active_by_weekday[weekday_index]
            time_per_user_values = time_per_user_by_weekday[weekday_index]
            avg_active = sum(active_values) / len(active_values) if active_values else 0.0
            avg_time_per_user = (
                sum(time_per_user_values) / len(time_per_user_values) if time_per_user_values else 0.0
            )
            weekday_points.append(
                {
                    "weekday": weekday_name,
                    "avg_active_participants": avg_active,
                    "avg_time_per_user_hours": avg_time_per_user,
                }
            )

        summary = self._build_summary(day_participants, day_seconds)
        return {"mode": "weekday_average", "points": weekday_points, "summary": summary}

    @staticmethod
    def _accumulate_by_local_day(
        start: datetime,
        end: datetime,
        tz,
        participant_id: int,
        day_participants: dict[date, set[int]],
        day_seconds: dict[date, float],
    ) -> None:
        start_local = start.astimezone(tz)
        end_local = end.astimezone(tz)
        cursor = start_local
        while cursor < end_local:
            next_midnight = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            segment_end = min(end_local, next_midnight)
            seconds = max(0.0, (segment_end - cursor).total_seconds())
            day = cursor.date()
            day_participants.setdefault(day, set()).add(participant_id)
            day_seconds[day] = day_seconds.get(day, 0.0) + seconds
            cursor = next_midnight

    @staticmethod
    def _build_summary(day_participants: dict[date, set[int]], day_seconds: dict[date, float]) -> dict:
        active_counts: list[int] = []
        daily_time_per_user_seconds: list[float] = []
        for day, users in day_participants.items():
            count = len(users)
            if count == 0:
                continue
            active_counts.append(count)
            daily_time_per_user_seconds.append(day_seconds.get(day, 0.0) / count)

        avg_active = sum(active_counts) / len(active_counts) if active_counts else 0.0
        avg_time_per_user_seconds = (
            sum(daily_time_per_user_seconds) / len(daily_time_per_user_seconds)
            if daily_time_per_user_seconds
            else 0.0
        )

        return {
            "avg_active_participants": avg_active,
            "avg_time_per_user_seconds": avg_time_per_user_seconds,
        }
