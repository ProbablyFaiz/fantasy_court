import { Loader2, Pause, Play } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

interface CaseAudioPlayerProps {
  audioUrl: string;
  startTime: number;
  endTime: number;
  episodeTitle: string;
}

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Plays only the [startTime, endTime] slice of an episode. The timeline, clock,
 * and scrubber are all relative to the segment, so the rest of the episode is
 * never visible or reachable.
 */
export default function CaseAudioPlayer({
  audioUrl,
  startTime,
  endTime,
  episodeTitle,
}: CaseAudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [failed, setFailed] = useState(false);
  // Seconds elapsed since startTime.
  const [position, setPosition] = useState(0);

  const duration = Math.max(0, endTime - startTime);

  // Moves the playhead to a segment-relative offset, clamped to the segment.
  const seekTo = useCallback(
    (offset: number) => {
      const audio = audioRef.current;
      if (!audio) return;
      const clamped = Math.min(Math.max(offset, 0), duration);
      audio.currentTime = startTime + clamped;
      setPosition(clamped);
    },
    [startTime, duration],
  );

  // While playing, poll the playhead every frame: smoother than timeupdate
  // (~4 Hz) and stops much closer to endTime.
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const tick = () => {
      const audio = audioRef.current;
      if (!audio) return;
      if (audio.currentTime >= endTime) {
        audio.pause();
        seekTo(0);
        return;
      }
      setPosition(Math.max(0, audio.currentTime - startTime));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, startTime, endTime, seekTo]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (!audio.paused) {
      audio.pause();
      return;
    }
    if (audio.currentTime < startTime || audio.currentTime >= endTime) {
      seekTo(0);
    }
    // play() rejects if interrupted by a pause or blocked by the browser;
    // the play/pause events keep our state accurate either way.
    audio.play().catch(() => {});
  };

  const handleLoadedMetadata = () => {
    const audio = audioRef.current;
    if (!audio) return;
    // The #t= fragment usually positions us already; this covers browsers
    // that ignore it.
    if (audio.currentTime < startTime || audio.currentTime >= endTime) {
      seekTo(0);
    }
  };

  return (
    <div className="bg-accent/5 rounded p-3 font-equity">
      {/* Media fragment: the browser starts loading and playing at startTime. */}
      {/* biome-ignore lint/a11y/useMediaCaption: no caption files exist; the opinion text on the page covers the segment. */}
      <audio
        ref={audioRef}
        src={`${audioUrl}#t=${startTime},${endTime}`}
        preload="metadata"
        onLoadedMetadata={handleLoadedMetadata}
        onPlay={() => setPlaying(true)}
        onPause={() => {
          setPlaying(false);
          setBuffering(false);
        }}
        onEnded={() => {
          setPlaying(false);
          seekTo(0);
        }}
        onWaiting={() => setBuffering(true)}
        onPlaying={() => setBuffering(false)}
        onSeeked={() => setBuffering(false)}
        onError={() => setFailed(true)}
      />

      {failed ? (
        <div className="text-sm text-foreground/60">
          Audio is unavailable for this case.
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={togglePlay}
            aria-label={
              playing ? `Pause ${episodeTitle}` : `Play ${episodeTitle}`
            }
            className="shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-accent hover:bg-accent/10 transition-colors cursor-pointer"
          >
            {playing && buffering ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : playing ? (
              <Pause className="w-5 h-5 fill-current" />
            ) : (
              <Play className="w-5 h-5 fill-current" />
            )}
          </button>

          <span className="shrink-0 text-xs tabular-nums text-foreground/80">
            {formatTime(position)}
          </span>

          <input
            type="range"
            min={0}
            max={duration}
            step={0.1}
            value={position}
            onChange={(e) => seekTo(Number(e.target.value))}
            aria-label="Seek"
            aria-valuetext={`${formatTime(position)} of ${formatTime(duration)}`}
            className="flex-1 min-w-0 h-1 accent-accent cursor-pointer"
          />

          <span className="shrink-0 text-xs tabular-nums text-foreground/80">
            {formatTime(duration)}
          </span>
        </div>
      )}

      <div className="mt-1 text-right text-xs text-foreground/50">
        Episode {formatTime(startTime)} – {formatTime(endTime)}
      </div>
    </div>
  );
}
