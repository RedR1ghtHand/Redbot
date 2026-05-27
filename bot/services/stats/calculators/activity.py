from datetime import datetime, timedelta, timezone

import settings
from database.repositories import StatsReadRepository


class ActivityCalculator:
    def __init__(self, stats_read_repository: StatsReadRepository):
        self.stats_read_repository = stats_read_repository

    async def compute(self, range_start: datetime, range_end: datetime) -> list[dict]:
        range_start = self.stats_read_repository.ensure_utc(range_start)
        range_end = self.stats_read_repository.ensure_utc(range_end)

        tz = settings.get_reporting_timezone()
        journals = await self.stats_read_repository.get_journals_overlapping_range(range_start, range_end)
        entries: list[tuple[int, datetime, datetime]] = []

        for entry in journals:
            joined_at = entry.get("user_joined_at")
            left_at = entry.get("user_left_at") or range_end
            user_data = entry.get("user_joined") or {}
            participant_id = user_data.get("member_id")

            if joined_at is None or participant_id is None:
                continue
            joined_at = self.stats_read_repository.ensure_utc(joined_at)
            left_at = self.stats_read_repository.ensure_utc(left_at)
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
