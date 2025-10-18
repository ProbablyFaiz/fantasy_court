# %%
"""Fix existing transcripts to account for buffer offsets in timestamps."""

import sqlalchemy as sa
from sqlalchemy.orm import selectinload

from court.db.models import EpisodeTranscript, FantasyCourtSegment
from court.db.session import get_session

SEGMENT_BUFFER_SECONDS = 60  # Must match the buffer used during transcription


def calculate_actual_segment_bounds(
    segment_start_s: float,
    segment_end_s: float,
    episode_duration_s: float | None,
    buffer_seconds: int = SEGMENT_BUFFER_SECONDS,
) -> tuple[float, float]:
    """
    Calculate the actual start and end times of a buffered segment.

    This replicates the logic from extract_segment_audio without loading audio.

    Args:
        segment_start_s: Original segment start time
        segment_end_s: Original segment end time
        episode_duration_s: Total episode duration (None if unknown)
        buffer_seconds: Buffer added on each side

    Returns:
        Tuple of (actual_start_s, actual_end_s)
    """
    # Calculate start/end with buffer (clamped to audio bounds)
    actual_start_s = max(0.0, segment_start_s - buffer_seconds)

    if episode_duration_s is not None:
        actual_end_s = min(episode_duration_s, segment_end_s + buffer_seconds)
    else:
        # If we don't know episode duration, assume buffer was applied
        actual_end_s = segment_end_s + buffer_seconds

    return actual_start_s, actual_end_s


# %%
# Get all transcripts with their segments and episodes
db = get_session()

transcripts = (
    db.execute(
        sa.select(EpisodeTranscript)
        .options(
            selectinload(EpisodeTranscript.segment).selectinload(
                FantasyCourtSegment.episode
            )
        )
        .where(EpisodeTranscript.segment_id.isnot(None))
    )
    .scalars()
    .all()
)

print(f"Found {len(transcripts)} transcripts to fix")

# %%
# Analyze and fix each transcript
fixed_count = 0
skipped_count = 0

for transcript in transcripts:
    segment = transcript.segment
    episode = segment.episode

    # Calculate what the actual bounds should have been
    actual_start_s, actual_end_s = calculate_actual_segment_bounds(
        segment.start_time_s,
        segment.end_time_s,
        episode.duration_seconds,
    )

    # Check current values in transcript JSON
    current_start = transcript.transcript_json.get("start_time_s")
    current_end = transcript.transcript_json.get("end_time_s")

    print(f"\nTranscript {transcript.id} (Episode: {episode.title[:40]}...)")
    print(f"  Segment bounds: {segment.start_time_s:.1f}s - {segment.end_time_s:.1f}s")
    print(f"  Current JSON bounds: {current_start:.1f}s - {current_end:.1f}s")
    print(f"  Expected actual bounds: {actual_start_s:.1f}s - {actual_end_s:.1f}s")

    # Check if this transcript needs fixing
    if current_start == segment.start_time_s and current_end == segment.end_time_s:
        print(
            "  -> Needs fixing: current bounds match segment (no buffer accounted for)"
        )

        # Calculate the offset we need to add to all segment timestamps
        # The diarized segments currently start at 0, but should start at actual_start_s
        timestamp_offset = actual_start_s

        # Update all segment timestamps
        updated_segments = []
        for seg in transcript.transcript_json["segments"]:
            updated_seg = seg.copy()
            updated_seg["start"] = seg["start"] + timestamp_offset
            updated_seg["end"] = seg["end"] + timestamp_offset
            updated_segments.append(updated_seg)

        # Update the transcript JSON
        transcript.transcript_json = {
            "segments": updated_segments,
            "start_time_s": actual_start_s,
            "end_time_s": actual_end_s,
        }

        fixed_count += 1
    elif current_start == actual_start_s and current_end == actual_end_s:
        print("  -> Already correct")
        skipped_count += 1
    else:
        print("  -> WARNING: Unexpected values, skipping")
        skipped_count += 1

# %%
# Show summary before committing
print(f"\n{'=' * 80}")
print("Summary:")
print(f"  Total transcripts: {len(transcripts)}")
print(f"  To be fixed: {fixed_count}")
print(f"  Skipped: {skipped_count}")
print(f"{'=' * 80}")

# %%
# Commit the changes
if fixed_count > 0:
    db.commit()
    print(f"\nCommitted {fixed_count} fixed transcripts to database")
else:
    print("\nNo transcripts needed fixing")

# %%
# Verify a sample transcript
if fixed_count > 0:
    sample = transcripts[0]
    print(f"\nSample fixed transcript {sample.id}:")
    print(f"  Start: {sample.transcript_json['start_time_s']:.1f}s")
    print(f"  End: {sample.transcript_json['end_time_s']:.1f}s")
    print(
        f"  First segment: {sample.transcript_json['segments'][0]['start']:.1f}s - {sample.transcript_json['segments'][0]['end']:.1f}s"
    )
    print(
        f"  Last segment: {sample.transcript_json['segments'][-1]['start']:.1f}s - {sample.transcript_json['segments'][-1]['end']:.1f}s"
    )

# %%
db.close()
