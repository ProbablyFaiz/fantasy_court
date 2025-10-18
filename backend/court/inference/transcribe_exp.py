# %%
"""Experimental script to test OpenAI's new speech-to-text diarization API."""

import base64
import tempfile
from pathlib import Path

import rl.utils.io
import sqlalchemy as sa
from openai import OpenAI
from pydub import AudioSegment

from court.db.models import FantasyCourtSegment, PodcastEpisode
from court.db.session import get_session
from court.utils import bucket

SPEAKER_SAMPLES_DIR = Path(__file__).parent / "speaker_samples"
MAX_CHUNK_DURATION_SECONDS = 1200  # OpenAI limit is 1400s, use 1200s for safety


def to_data_url(path: Path) -> str:
    """Convert a file to a data URL for use with OpenAI API."""
    with path.open("rb") as fh:
        return "data:audio/wav;base64," + base64.b64encode(fh.read()).decode("utf-8")


def split_mp3_by_duration(
    mp3_data: bytes, max_duration_seconds: int = MAX_CHUNK_DURATION_SECONDS
) -> list[Path]:
    """
    Split an MP3 file into multiple temporary files, each under max_duration_seconds.

    Returns:
        List of Path objects pointing to temporary MP3 files
    """
    # Load the audio data
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".mp3", delete=False
    ) as tmp_input:
        tmp_input.write(mp3_data)
        tmp_input_path = Path(tmp_input.name)

    audio = AudioSegment.from_mp3(tmp_input_path)
    tmp_input_path.unlink()  # Clean up input temp file

    total_duration_ms = len(audio)
    max_duration_ms = max_duration_seconds * 1000

    # If the original is already short enough, just return it as a single chunk
    if total_duration_ms <= max_duration_ms:
        tmp_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".mp3", delete=False)
        tmp_file.write(mp3_data)
        tmp_file.close()
        return [Path(tmp_file.name)]

    # Split into chunks
    chunk_paths = []
    start_ms = 0

    while start_ms < total_duration_ms:
        end_ms = min(start_ms + max_duration_ms, total_duration_ms)
        chunk = audio[start_ms:end_ms]

        # Export chunk to temp file
        tmp_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".mp3", delete=False)
        chunk.export(tmp_file.name, format="mp3")
        tmp_file.close()
        chunk_paths.append(Path(tmp_file.name))

        start_ms = end_ms

    return chunk_paths


# %%
# Load OpenAI API key
OPENAI_API_KEY = rl.utils.io.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# %%
# Query database for an episode with a fantasy court segment and non-null bucket path
db = get_session()

query = (
    sa.select(PodcastEpisode)
    .join(FantasyCourtSegment)
    .where(PodcastEpisode.bucket_mp3_path.isnot(None))
    .limit(1)
)

episode = db.execute(query).scalar_one_or_none()

if episode is None:
    raise ValueError("No episode found with fantasy court segment and bucket path")

print(f"Found episode: {episode.title}")
print(f"Bucket path: {episode.bucket_mp3_path}")
print(
    f"Fantasy court segment: {episode.fantasy_court_segment.start_time_s}s - {episode.fantasy_court_segment.end_time_s}s"
)

# %%
# Load MP3 from bucket
s3_client = bucket.get_bucket_client()
mp3_data = bucket.read_file(episode.bucket_mp3_path, s3_client)

print(f"Loaded {len(mp3_data)} bytes from bucket")

# %%
# Load speaker reference samples
speaker_names = [
    {
        "name": "Craig Horlbeck",
        "file_name": "Craig.wav",
    },
    {
        "name": "Danny Kelly",
        "file_name": "DK.wav",
    },
    {
        "name": "Danny Heifetz",
        "file_name": "Heifetz.wav",
    },
]
speaker_references = [
    to_data_url(SPEAKER_SAMPLES_DIR / speaker["file_name"]) for speaker in speaker_names
]

print(
    f"Loaded {len(speaker_references)} speaker reference samples: {', '.join([speaker['name'] for speaker in speaker_names])}"
)

# %%
# Split MP3 into chunks if necessary (max 1200 seconds per chunk)
chunk_paths = split_mp3_by_duration(mp3_data)
print(f"Split MP3 into {len(chunk_paths)} chunk(s)")

# Display chunk sizes and durations
for i, chunk_path in enumerate(chunk_paths, 1):
    size_mb = chunk_path.stat().st_size / (1024 * 1024)
    # Load to get duration
    chunk_audio = AudioSegment.from_mp3(str(chunk_path))
    duration_seconds = len(chunk_audio) / 1000
    print(f"  Chunk {i}: {size_mb:.2f} MB, {duration_seconds:.1f}s")


# %%

# Transcribe each chunk
all_transcripts = []

for i, chunk_path in enumerate(chunk_paths, 1):
    print(f"\nTranscribing chunk {i}/{len(chunk_paths)}...")

    with chunk_path.open("rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-transcribe-diarize",
            file=audio_file,
            response_format="diarized_json",
            chunking_strategy="auto",
            extra_body={
                "known_speaker_names": [speaker["name"] for speaker in speaker_names],
                "known_speaker_references": speaker_references,
            },
        )

    # Adjust timestamps to account for chunk offset
    all_transcripts.append(transcript)
    print(f"  Got {len(transcript.segments)} segments from chunk {i}")

# %%
# Display results
print(f"\nTranscript with {len(all_transcripts)} transcripts:")
print("-" * 80)

current_buffer = ""
current_speaker = None
for transcript in all_transcripts:
    for segment in transcript.segments:
        if segment.speaker != current_speaker:
            print(f"  {current_speaker}: {current_buffer}")
            current_buffer = ""
            current_speaker = segment.speaker
        current_buffer += segment.text
    print(f"  {current_speaker}: {current_buffer}")

# %%
# Clean up
db.close()
