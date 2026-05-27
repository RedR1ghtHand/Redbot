from datetime import datetime, timezone

from database.repositories import StatsReadRepository


class SnapshotCalculator:
    def __init__(self, stats_read_repository: StatsReadRepository):
        self.stats_read_repository = stats_read_repository

    async def compute(
        self,
        range_start: datetime,
        range_end: datetime,
        top_limit: int = 10,
    ) -> dict:
        range_start = self.stats_read_repository.ensure_utc(range_start)
        range_end = self.stats_read_repository.ensure_utc(range_end)

        sessions = await self.stats_read_repository.get_sessions_in_range(range_start, range_end)
        sessions_for_journal = await self.stats_read_repository.get_sessions_overlapping_range(range_start, range_end)
        session_ids = [
            session.get("channel_id") for session in sessions_for_journal if session.get("channel_id") is not None
        ]
        journals = await self.stats_read_repository.get_journals_by_session_ids(session_ids)
        members = await self.stats_read_repository.get_all_members()

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
            joined_at = self.stats_read_repository.ensure_utc(joined_at)
            if left_at is not None:
                left_at = self.stats_read_repository.ensure_utc(left_at)
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
