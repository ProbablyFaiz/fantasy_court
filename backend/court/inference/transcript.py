"""Pydantic models and utilities for working with transcripts."""

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """A single diarized segment within a transcript."""

    id: str
    """Unique identifier for the segment."""
    start: float
    """Start timestamp in seconds (relative to episode start)."""
    end: float
    """End timestamp in seconds (relative to episode start)."""
    speaker: str
    """Speaker label (either from known speakers or A, B, C, etc.)."""
    text: str
    """Transcript text for this segment."""
    type: str = Field(default="transcript.text.segment")
    """The type of the segment."""


class SpeakerUtterance(BaseModel):
    """A continuous utterance by a single speaker, combining multiple segments."""

    speaker: str
    """Speaker label."""
    start: float
    """Start timestamp in seconds (from the first segment)."""
    end: float
    """End timestamp in seconds (from the last segment)."""
    text: str
    """Combined text from all segments in this utterance."""


class Transcript(BaseModel):
    """Full transcript with diarized segments."""

    segments: list[TranscriptSegment]
    """List of diarized transcript segments."""

    def get_utterances(self) -> list[SpeakerUtterance]:
        """Group consecutive segments by speaker into continuous utterances."""
        if not self.segments:
            return []

        utterances: list[SpeakerUtterance] = []
        current_speaker: str | None = None
        current_start: float | None = None
        current_end: float | None = None
        current_text_parts: list[str] = []

        for segment in self.segments:
            if segment.speaker != current_speaker:
                # Save previous utterance if exists
                if current_speaker is not None:
                    utterances.append(
                        SpeakerUtterance(
                            speaker=current_speaker,
                            start=current_start,
                            end=current_end,
                            text="".join(current_text_parts),
                        )
                    )

                # Start new utterance
                current_speaker = segment.speaker
                current_start = segment.start
                current_end = segment.end
                current_text_parts = [segment.text]
            else:
                # Continue current utterance
                current_end = segment.end
                current_text_parts.append(segment.text)

        # Don't forget the last utterance
        if current_speaker is not None:
            utterances.append(
                SpeakerUtterance(
                    speaker=current_speaker,
                    start=current_start,
                    end=current_end,
                    text="".join(current_text_parts),
                )
            )

        return utterances

    def to_string(self, include_timestamps: bool = True) -> str:
        """
        Convert transcript to a human-readable string representation.

        Args:
            include_timestamps: If True, include start-end timestamps for each utterance

        Returns:
            Formatted string with speaker labels and their utterances
        """
        utterances = self.get_utterances()
        lines = []

        for utterance in utterances:
            if include_timestamps:
                timestamp_str = f"[{utterance.start:.1f}s - {utterance.end:.1f}s]"
                lines.append(f"{utterance.speaker} {timestamp_str}: {utterance.text}")
            else:
                lines.append(f"{utterance.speaker}: {utterance.text}")

        return "\n".join(lines)

    def __str__(self) -> str:
        """String representation with timestamps."""
        return self.to_string(include_timestamps=True)
