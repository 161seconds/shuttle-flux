import React, { useState, useEffect, useRef } from "react";
import {
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  Activity,
  Video,
  Columns,
  Square,
  Eye,
  EyeOff,
  Sparkles,
  Layers,
} from "lucide-react";
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
  const [viewMode, setViewMode] = useState<"dual" | "single">("dual");
  const [showOverlays, setShowOverlays] = useState(true);
  const [isPlaying, setIsPlaying] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isMuted, setIsMuted] = useState(true);
  const [videoError, setVideoError] = useState(false);

  const rawVideoRef = useRef<HTMLVideoElement>(null);
  const aiVideoRef = useRef<HTMLVideoElement>(null);

  const duration = analytics.metadata.duration_seconds || 30;
  const frameRecords = analytics.frame_records || [];
  const matchId = analytics.metadata.match_id;
  const videoSrc = `${API_BASE_URL}/api/v1/matches/${matchId}/video`;

  // Seek both videos to rally timestamp when clicked from timeline
  useEffect(() => {
    if (selectedRallyTime !== undefined && selectedRallyTime !== null) {
      handleSeek(selectedRallyTime);
      setIsPlaying(true);
    }
  }, [selectedRallyTime]);

  // Sync play/pause on both video elements
  useEffect(() => {
    if (!videoError) {
      if (isPlaying) {
        rawVideoRef.current?.play().catch(() => {});
        aiVideoRef.current?.play().catch(() => {});
      } else {
        rawVideoRef.current?.pause();
        aiVideoRef.current?.pause();
      }
    }
  }, [isPlaying, videoError, viewMode]);

  // Sync playback speed on both video elements
  useEffect(() => {
    if (rawVideoRef.current) rawVideoRef.current.playbackRate = playbackSpeed;
    if (aiVideoRef.current) aiVideoRef.current.playbackRate = playbackSpeed;
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
    if (aiVideoRef.current && !videoError) {
      const t = aiVideoRef.current.currentTime;
      setCurrentTime(t);
      // Synchronize raw video if it drifts by more than 0.08s
      if (rawVideoRef.current && Math.abs(rawVideoRef.current.currentTime - t) > 0.08) {
        rawVideoRef.current.currentTime = t;
      }
    }
  };

  const handleSeek = (time: number) => {
    setCurrentTime(time);
    if (!videoError) {
      if (rawVideoRef.current) rawVideoRef.current.currentTime = time;
      if (aiVideoRef.current) aiVideoRef.current.currentTime = time;
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
      {/* Header Bar with View Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5 border-b border-gray-800 pb-4">
        <div className="flex items-center space-x-3">
          <Activity className="w-5 h-5 text-brand-cyan" />
          <h3 className="font-bold text-lg text-white">Match Visualizer & Synchronized Dual Radar</h3>
        </div>

        <div className="flex items-center flex-wrap gap-2">
          {/* Mode Switcher: Dual vs Single */}
          <div className="flex items-center bg-surface-light p-1 rounded-xl border border-gray-800">
            <button
              onClick={() => setViewMode("dual")}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                viewMode === "dual"
                  ? "bg-brand-cyan text-black shadow-md shadow-cyan-500/30"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              <Columns className="w-3.5 h-3.5" />
              <span>Phát Song Song (Dual Sync)</span>
            </button>
            <button
              onClick={() => setViewMode("single")}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                viewMode === "single"
                  ? "bg-brand-cyan text-black shadow-md shadow-cyan-500/30"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              <Square className="w-3.5 h-3.5" />
              <span>Màn Hình Đơn</span>
            </button>
          </div>

          {/* Toggle AI Overlays */}
          <button
            onClick={() => setShowOverlays(!showOverlays)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all ${
              showOverlays
                ? "bg-cyan-950/60 border-cyan-700 text-cyan-300"
                : "bg-surface border-gray-800 text-gray-400 hover:text-gray-200"
            }`}
          >
            {showOverlays ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>{showOverlays ? "Ẩn Khung AI" : "Hiện Khung AI"}</span>
          </button>
        </div>
      </div>

      {/* Main Dual Player / Single Player Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* Video Player Area: Takes 3 Columns in XL or Full */}
        <div className="xl:col-span-3 flex flex-col justify-between space-y-4">
          <div
            className={`grid gap-4 ${
              viewMode === "dual" ? "grid-cols-1 md:grid-cols-2" : "grid-cols-1"
            }`}
          >
            {/* Screen 1: Original Raw Video Footage */}
            {viewMode === "dual" && (
              <div className="relative aspect-video w-full rounded-2xl overflow-hidden bg-black border border-gray-800 shadow-xl flex flex-col justify-between">
                {/* Header Tag */}
                <div className="absolute top-3 left-3 z-10 flex items-center space-x-1.5 bg-black/80 backdrop-blur-md px-2.5 py-1 rounded-lg border border-gray-700/80 text-[11px] font-bold text-gray-200 shadow-lg">
                  <Video className="w-3.5 h-3.5 text-red-500" />
                  <span>Video Gốc (Raw Footage)</span>
                </div>

                {!videoError ? (
                  <video
                    ref={rawVideoRef}
                    src={videoSrc}
                    playsInline
                    muted={true}
                    autoPlay
                    onEnded={() => setIsPlaying(false)}
                    className="w-full h-full object-contain bg-black"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gray-950 text-gray-500 text-xs">
                    Raw Video Stream
                  </div>
                )}
              </div>
            )}

            {/* Screen 2: AI Computer Vision & Tracking Stream */}
            <div className="relative aspect-video w-full rounded-2xl overflow-hidden bg-black border border-gray-800 shadow-xl flex flex-col justify-between">
              {/* Header Tag */}
              <div className="absolute top-3 left-3 z-10 flex items-center space-x-1.5 bg-black/80 backdrop-blur-md px-2.5 py-1 rounded-lg border border-cyan-500/40 text-[11px] font-bold text-cyan-300 shadow-lg">
                <Sparkles className="w-3.5 h-3.5 text-brand-cyan" />
                <span>AI Vision & Tracking</span>
              </div>

              {!videoError ? (
                <video
                  ref={aiVideoRef}
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

              {/* Synchronized AI Tracking Overlays */}
              {showOverlays && currentFrame && (
                <div className="absolute inset-0 pointer-events-none p-3 flex flex-col justify-between z-10">
                  <div className="flex justify-between items-center text-[11px] font-mono text-cyan-300 bg-black/80 px-2.5 py-1 rounded-lg border border-cyan-500/30 w-fit backdrop-blur-md self-end mt-1 shadow-md">
                    <span>FRAME: {currentFrame.frame_idx}</span>
                    <span className="ml-2.5">TIME: {currentTime.toFixed(2)}s</span>
                  </div>

                  {/* Player Bounding Box Overlay */}
                  <div className="absolute inset-0">
                    {currentFrame.players.map((p) => {
                      let left = `${p.x_norm * 80 + 10}%`;
                      let top = p.player_id === 1 ? "64%" : "24%";
                      let width = "3.5rem";
                      let height = "6rem";

                      if (p.bbox_norm && p.bbox_norm.length === 4) {
                        const [bx1, by1, bx2, by2] = p.bbox_norm;
                        left = `${Math.max(0, Math.min(95, bx1 * 100))}%`;
                        top = `${Math.max(0, Math.min(90, by1 * 100))}%`;
                        width = `${Math.max(4, Math.min(40, (bx2 - bx1) * 100))}%`;
                        height = `${Math.max(6, Math.min(60, (by2 - by1) * 100))}%`;
                      }

                      const color =
                        p.player_id === 1
                          ? "border-brand-cyan text-brand-cyan shadow-cyan-500/40"
                          : "border-brand-amber text-brand-amber shadow-amber-500/40";

                      const confText = p.confidence ? `${Math.round(p.confidence * 100)}%` : "AI";

                      return (
                        <div
                          key={p.player_id}
                          className={`absolute border-2 ${color} rounded-lg transition-all duration-75 flex flex-col justify-between p-1 bg-black/30 backdrop-blur-[1px] shadow-lg`}
                          style={{ top, left, width, height }}
                        >
                          <div className="flex items-center space-x-1 bg-black/90 px-1 py-0.5 rounded text-white w-fit">
                            <span className="text-[9px] font-black">P{p.player_id}</span>
                            <span className="text-[8px] opacity-75">{confText}</span>
                          </div>
                          <div className="w-2 h-2 rounded-full bg-white mx-auto shadow-sm shadow-white"></div>
                        </div>
                      );
                    })}

                    {/* Shuttlecock Overlay */}
                    {currentFrame.shuttle && currentFrame.shuttle.visible && (
                      <div
                        className="absolute w-3.5 h-3.5 rounded-full bg-amber-300 border-2 border-white shadow-lg shadow-yellow-400 transition-all duration-75 z-20"
                        style={{
                          top: `${
                            currentFrame.shuttle.center_norm
                              ? currentFrame.shuttle.center_norm[1] * 100
                              : currentFrame.shuttle.y_norm * 75 + 12
                          }%`,
                          left: `${
                            currentFrame.shuttle.center_norm
                              ? currentFrame.shuttle.center_norm[0] * 100
                              : currentFrame.shuttle.x_norm * 78 + 11
                          }%`,
                        }}
                      ></div>
                    )}
                  </div>

                  <div className="text-right text-[10px] text-gray-400 bg-black/70 px-2 py-0.5 rounded-md w-fit self-end font-mono border border-gray-800">
                    <span>YOLOv8 + ByteTrack v2</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Unified Timeline & Master Controls Bar */}
          <div className="p-3.5 bg-surface rounded-2xl border border-gray-800 flex flex-col space-y-2.5 shadow-lg">
            {/* Scrubber */}
            <div className="flex items-center space-x-3">
              <span className="text-xs font-mono text-cyan-400 font-bold w-12">{currentTime.toFixed(1)}s</span>
              <input
                type="range"
                min="0"
                max={duration}
                step="0.05"
                value={currentTime}
                onChange={(e) => handleSeek(parseFloat(e.target.value))}
                className="w-full h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-brand-cyan"
              />
              <span className="text-xs font-mono text-gray-400 w-12 text-right">{duration.toFixed(1)}s</span>
            </div>

            {/* Playback Buttons */}
            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="px-3 py-2 rounded-xl bg-brand-cyan hover:bg-cyan-300 text-black font-bold text-xs flex items-center space-x-1.5 transition-all shadow-md shadow-cyan-500/20 active:scale-95"
                >
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  <span>{isPlaying ? "Tạm dừng" : "Phát video"}</span>
                </button>
                <button
                  onClick={() => handleSeek(0)}
                  className="p-2 rounded-xl bg-surface-light hover:bg-gray-700 text-gray-300 transition-colors"
                  title="Phát lại từ đầu"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
                {!videoError && (
                  <button
                    onClick={() => setIsMuted(!isMuted)}
                    className={`p-2 rounded-xl border transition-colors ${
                      !isMuted
                        ? "bg-cyan-950/60 border-cyan-700 text-cyan-300"
                        : "bg-surface-light border-transparent text-gray-400 hover:text-gray-200"
                    }`}
                    title={isMuted ? "Bật âm thanh" : "Tắt âm thanh"}
                  >
                    {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                  </button>
                )}
              </div>

              {/* Speed Buttons */}
              <div className="flex items-center space-x-1.5 text-xs">
                <span className="text-[11px] text-gray-500 font-medium mr-1">Tốc độ:</span>
                {[0.5, 1, 1.5, 2].map((spd) => (
                  <button
                    key={spd}
                    onClick={() => setPlaybackSpeed(spd)}
                    className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
                      playbackSpeed === spd
                        ? "bg-brand-cyan text-black shadow-sm"
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
        <div className="flex flex-col items-center justify-between p-3 glass-panel rounded-2xl border border-gray-800 shadow-xl">
          <div className="w-full flex items-center justify-between mb-2 border-b border-gray-800 pb-2">
            <span className="text-xs font-bold text-gray-300 uppercase tracking-wider">2D Court Radar</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
              Live Homography
            </span>
          </div>

          <RadarCanvas currentFrame={currentFrame} width={260} height={460} />

          <div className="w-full mt-3 pt-2 border-t border-gray-800/80 flex items-center justify-between text-[11px] text-gray-400">
            <div className="flex items-center space-x-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-brand-cyan" />
              <span>P1 (Gần)</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-brand-amber" />
              <span>P2 (Xa)</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-amber-300" />
              <span>Quả cầu</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
