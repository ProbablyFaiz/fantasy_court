import { useEffect, useRef } from "react";
import AudioPlayer from "react-h5-audio-player";
import "react-h5-audio-player/lib/styles.css";

interface CaseAudioPlayerProps {
  audioUrl: string;
  startTime: number;
  endTime: number;
  episodeTitle: string;
}

export default function CaseAudioPlayer({
  audioUrl,
  startTime,
  endTime,
}: CaseAudioPlayerProps) {
  const playerRef = useRef<AudioPlayer>(null);

  useEffect(() => {
    const audio = playerRef.current?.audio.current;
    if (!audio) return;

    let hasSetInitialTime = false;

    // Set initial time when loaded
    const handleLoadedMetadata = () => {
      if (!hasSetInitialTime) {
        audio.currentTime = startTime;
        hasSetInitialTime = true;
      }
    };

    // Also try on canplay in case loadedmetadata already fired
    const handleCanPlay = () => {
      if (!hasSetInitialTime) {
        audio.currentTime = startTime;
        hasSetInitialTime = true;
      }
    };

    // Stop playback when reaching end time and prevent seeking outside range
    const handleTimeUpdate = () => {
      // Enforce end boundary
      if (audio.currentTime >= endTime) {
        audio.pause();
        audio.currentTime = startTime;
        hasSetInitialTime = true;
      }
      // Enforce start boundary (if user seeks backwards)
      else if (audio.currentTime < startTime && hasSetInitialTime) {
        audio.currentTime = startTime;
      }
    };

    // Try to set immediately if already loaded
    if (audio.readyState >= 1 && !hasSetInitialTime) {
      audio.currentTime = startTime;
      hasSetInitialTime = true;
    }

    audio.addEventListener("loadedmetadata", handleLoadedMetadata);
    audio.addEventListener("canplay", handleCanPlay);
    audio.addEventListener("timeupdate", handleTimeUpdate);

    return () => {
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audio.removeEventListener("canplay", handleCanPlay);
      audio.removeEventListener("timeupdate", handleTimeUpdate);
    };
  }, [startTime, endTime]);

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    }
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="case-audio-player bg-accent/5 rounded p-3 relative pb-5">
      <AudioPlayer
        ref={playerRef}
        src={audioUrl}
        showJumpControls={false}
        customAdditionalControls={[]}
        customVolumeControls={[]}
        layout="horizontal-reverse"
        className="shadow-none"
      />
      <div className="absolute bottom-2 right-3 text-xs text-foreground/50 font-equity">
        {formatTime(startTime)} – {formatTime(endTime)}
      </div>
    </div>
  );
}
