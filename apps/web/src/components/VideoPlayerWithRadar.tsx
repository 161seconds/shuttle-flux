import React, { useState, useEffect, useRef } from "react";
import { Play, Pause, RotateCcw, Volume2, VolumeX, Maximize2, Activity, Video } from "lucide-react";
import { MatchAnalytics, FrameRecord, API_BASE_URL } from "../lib/api";
import { RadarCanvas } from "./RadarCanvas";

interface VideoPlayerWithRadarProps {
  analytics: MatchAnalytics;
  selectedRallyTime?: number | null;
}

export const VideoPlayerWithRadar: React.FC<VideoPlayerWithRadarProps> = ({
  analytics,
  selectedRallyTime,
}) => {
  const [isPlaying, setIsPlaying] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isMuted, setIsMuted] = useState(true);
  const [videoError, setVideoError] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const duration = analytics.metadata.duration_seconds || 30;
  const frameRecords = analytics.frame_records || [];
  const matchId = analytics.metadata.match_id;
  const videoSrc = `${API_BASE_URL}/api/v1/matches/${matchId}/video`;

  // Seek to rally time if user clicks a rally in timeline
  useEffect(() => {
    if (selectedRallyTime !== undefined && selectedRallyTime !== null) {
      setCurrentTime(selectedRallyTime);
      if (videoRef.current) {
        videoRef.current.currentTime = selectedRallyTime;
      }
      setIsPlaying(true);
    }
  }, [selectedRallyTime]);

  // Sync play/pause with video element
  useEffect(() => {
    if (videoRef.current && !videoError) {
      if (isPlaying) {
        videoRef.current.play().catch(() => {});
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying, videoError]);

  // Sync playback speed
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed]);

  // Fallback simulation timer if video tag fails or backend video not present
  useEffect(() => {
    let interval: any = null;
    if (isPlaying && videoError) {
      interval = setInterval(() => {
        setCurrentTime((prev) => {
          const next = prev + 0.05 * playbackSpeed;
          return next >= duration ? 0 : next;
        });
      }, 50);
    }
    return () => clearInterval(interval);
  }, [isPlaying, playbackSpeed, duration, videoError]);

  const handleTimeUpdate = () => {
    if (videoRef.current && !videoError) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleSeek = (time: number) => {
    setCurrentTime(time);
    if (videoRef.current && !videoError) {
      videoRef.current.currentTime = time;
    }
  };

  // Find matching frame record for current timestamp
  const currentFrame = frameRecords.reduce<FrameRecord | undefined>((prev, curr) => {
    if (!prev) return curr;
    return Math.abs(curr.timestamp - currentTime) < Math.abs(prev.timestamp - currentTime)
      ? curr
      : prev;
  }, undefined);

  return (
    <div className="glass-panel rounded-2xl p-6 border border-gray-700 shadow-2xl mb-8">
      <div className="flex items-center justify-between mb-4 border-b border-gray-800 pb-3">
        <div className="flex items-center space-x-2">
          <Activity className="w-5 h-5 text-brand-cyan" />
          <h3 className="font-bold text-lg text-white">Match Visualizer & 2D Top-down Radar</h3>
        </div>
        <div className="flex items-center space-x-2">
          {!videoError ? (
            <span className="text-xs px-2.5 py-1 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-400 font-semibold flex items-center space-x-1.5">
              <Video className="w-3.5 h-3.5" />
              <span>Real Video Stream</span>
            </span>
          ) : (
            <span className="text-xs px-2.5 py-1 rounded bg-surface border border-gray-700 text-gray-300">
              Synthetic Simulation View
            </span>
          )}
          <span className="text-xs px-2.5 py-1 rounded bg-surface border border-gray-700 text-cyan-400 font-mono">
            Homography Active
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Video Player with AI Overlays */}
        <div className="lg:col-span-2 flex flex-col justify-between">
          <div className="relative aspect-video w-full rounded-xl overflow-hidden bg-black border border-gray-800 shadow-inner flex items-center justify-center">
            {/* Real HTML5 Video Player */}
            {!videoError ? (
              <video
                ref={videoRef}
                src={videoSrc}
                playsInline
                muted={isMuted}
                autoPlay
                onTimeUpdate={handleTimeUpdate}
                onEnded={() => setIsPlaying(false)}
                onError={() => setVideoError(true)}
                className="w-full h-full object-contain bg-black"
              />
            ) : (
              /* Fallback Synthetic Court Visualizer */
              <div className="absolute inset-0 bg-gradient-to-t from-gray-950 via-slate-900 to-black flex items-center justify-center opacity-90">
                <div className="w-4/5 h-4/5 border-2 border-emerald-600/40 rounded-lg transform -perspective-500 rotate-x-12 relative flex items-center justify-center">
                  <div className="w-full h-0.5 bg-cyan-400/60 absolute top-1/2"></div>
                  <span className="text-xs text-emerald-500/50 font-mono">BADMINTON COURT CAMERA VIEW</span>
                </div>
              </div>
            )}

            {/* Live AI Detection & Tracking Overlays */}
            {currentFrame && (
              <div className="absolute inset-0 pointer-events-none p-4 flex flex-col justify-between">
                <div className="flex justify-between items-center text-xs font-mono text-cyan-300 bg-black/70 px-3 py-1.5 rounded-lg border border-cyan-500/30 w-fit backdrop-blur-sm shadow-md">
                  <span>FRAME: {currentFrame.frame_idx}</span>
                  <span className="ml-3">TIME: {currentTime.toFixed(2)}s</span>
                </div>

                {/* Player Bounding Box Overlay */}
                <div className="absolute inset-0">
                  {currentFrame.players.map((p) => {
                    const top = p.player_id === 1 ? "65%" : "25%";
                    const left = `${p.x_norm * 80 + 10}%`;
                    const color =
                      p.player_id === 1
                        ? "border-brand-cyan text-brand-cyan shadow-cyan-500/30"
                        : "border-brand-amber text-brand-amber shadow-amber-500/30";

                    return (
                      <div
                        key={p.player_id}
                        className={`absolute w-16 h-28 border-2 ${color} rounded-lg transition-all duration-75 flex flex-col justify-between p-1.5 bg-black/30 backdrop-blur-[2px] shadow-lg`}
                        style={{ top, left }}
                      >
                        <span className="text-[10px] font-black bg-black/80 px-1.5 py-0.5 rounded text-white w-fit">
                          P{p.player_id}
                        </span>
                        <div className="w-2.5 h-2.5 rounded-full bg-white mx-auto shadow-sm shadow-white"></div>
                      </div>
                    );
                  })}

                  {/* Shuttlecock Overlay */}
                  {currentFrame.shuttle && currentFrame.shuttle.visible && (
                    <div
                      className="absolute w-3.5 h-3.5 rounded-full bg-amber-300 border-2 border-white shadow-lg shadow-yellow-400 transition-all duration-75"
                      style={{
                        top: `${currentFrame.shuttle.y_norm * 75 + 12}%`,
                        left: `${currentFrame.shuttle.x_norm * 78 + 11}%`,
                      }}
                    ></div>
                  )}
                </div>

                <div className="text-right text-[11px] text-gray-400 bg-black/50 px-2 py-1 rounded w-fit self-end font-mono">
                  <span>YOLOv8 + ByteTrack v2</span>
                </div>
              </div>
            )}
          </div>

          {/* Timeline & Controls Bar */}
          <div className="mt-4 p-3 bg-surface rounded-xl border border-gray-800 flex flex-col space-y-2">
            {/* Scrubber */}
            <div className="flex items-center space-x-3">
              <span className="text-xs font-mono text-gray-400 w-12">{currentTime.toFixed(1)}s</span>
              <input
                type="range"
                min="0"
                max={duration}
                step="0.05"
                value={currentTime}
                onChange={(e) => handleSeek(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-brand-cyan"
              />
              <span className="text-xs font-mono text-gray-400 w-12">{duration.toFixed(1)}s</span>
            </div>

            {/* Playback Buttons */}
            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="p-2 rounded-lg bg-surface-light hover:bg-gray-700 text-white transition-colors"
                >
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </button>
                <button
                  onClick={() => handleSeek(0)}
                  className="p-2 rounded-lg bg-surface-light hover:bg-gray-700 text-gray-300 transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
                {!videoError && (
                  <button
                    onClick={() => setIsMuted(!isMuted)}
                    className="p-2 rounded-lg bg-surface-light hover:bg-gray-700 text-gray-300 transition-colors"
                    title={isMuted ? "Unmute" : "Mute"}
                  >
                    {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                  </button>
                )}
              </div>

              {/* Speed Buttons */}
              <div className="flex items-center space-x-1 text-xs">
                {[0.5, 1, 1.5, 2].map((spd) => (
                  <button
                    key={spd}
                    onClick={() => setPlaybackSpeed(spd)}
                    className={`px-2 py-1 rounded font-semibold transition-colors ${
                      playbackSpeed === spd
                        ? "bg-brand-cyan text-black"
                        : "bg-surface-light text-gray-400 hover:text-white"
                    }`}
                  >
                    {spd}x
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right 1 Col: 2D Radar Canvas */}
        <div className="flex flex-col items-center justify-center p-2">
          <RadarCanvas currentFrame={currentFrame} width={260} height={460} />
        </div>
      </div>
    </div>
  );
};
