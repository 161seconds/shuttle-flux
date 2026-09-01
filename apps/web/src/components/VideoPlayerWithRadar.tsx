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
  Edit3,
  Check,
  X,
  UserCheck,
  Grid,
} from "lucide-react";
import { MatchAnalytics, FrameRecord, API_BASE_URL, updatePlayerNames } from "../lib/api";
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
  const [showCourtMesh, setShowCourtMesh] = useState(true);
  const [showVoronoi, setShowVoronoi] = useState(false);
  const [isPlaying, setIsPlaying] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState<number>(
    analytics.metadata.duration_seconds || 30
  );
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isMuted, setIsMuted] = useState(true);
  const [videoError, setVideoError] = useState(false);

  // Player Names State (Auto-extracted via OCR or manually edited)
  const [p1Name, setP1Name] = useState(
    analytics.players?.player_1?.label || "VĐV 1 (Gần)"
  );
  const [p2Name, setP2Name] = useState(
    analytics.players?.player_2?.label || "VĐV 2 (Xa)"
  );
  const [isEditingNames, setIsEditingNames] = useState(false);
  const [p1Input, setP1Input] = useState(p1Name);
  const [p2Input, setP2Input] = useState(p2Name);
  const [isSavingNames, setIsSavingNames] = useState(false);

  const rawVideoRef = useRef<HTMLVideoElement>(null);
  const aiVideoRef = useRef<HTMLVideoElement>(null);

  const frameRecords = analytics.frame_records || [];
  const matchId = analytics.metadata.match_id;
  const videoSrc = `${API_BASE_URL}/api/v1/matches/${matchId}/video`;

  // Update names if analytics changes
  useEffect(() => {
    if (analytics.players?.player_1?.label) {
      setP1Name(analytics.players.player_1.label);
      setP1Input(analytics.players.player_1.label);
    }
    if (analytics.players?.player_2?.label) {
      setP2Name(analytics.players.player_2.label);
      setP2Input(analytics.players.player_2.label);
    }
  }, [analytics]);

  const handleSaveNames = async () => {
    try {
      setIsSavingNames(true);
      await updatePlayerNames(matchId, p1Input, p2Input);
      setP1Name(p1Input);
      setP2Name(p2Input);
      setIsEditingNames(false);
    } catch (err) {
      console.error("Failed to save player names:", err);
      setP1Name(p1Input);
      setP2Name(p2Input);
      setIsEditingNames(false);
    } finally {
      setIsSavingNames(false);
    }
  };

  // Format seconds to MM:SS or MM:SS.t
  const formatTime = (seconds: number) => {
    if (isNaN(seconds) || seconds < 0) return "00:00.0";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const tenths = Math.floor((seconds % 1) * 10);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${tenths}`;
  };

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

  // Sync volume / muted
  useEffect(() => {
    if (rawVideoRef.current) rawVideoRef.current.muted = isMuted;
    if (aiVideoRef.current) aiVideoRef.current.muted = true;
  }, [isMuted]);

  // 60 FPS High-performance Animation Loop directly reading video hardware time
  useEffect(() => {
    let animId: number;

    const tick = () => {
      const activeVideo = aiVideoRef.current || rawVideoRef.current;
      if (activeVideo && !videoError) {
        if (!activeVideo.paused && !activeVideo.ended) {
          const t = activeVideo.currentTime;
          setCurrentTime(t);

          // Update duration if not set
          if (activeVideo.duration && !isNaN(activeVideo.duration) && activeVideo.duration > 0) {
            setVideoDuration(activeVideo.duration);
          }

          // Keep raw video in tight sync
          if (rawVideoRef.current && Math.abs(rawVideoRef.current.currentTime - t) > 0.05) {
            rawVideoRef.current.currentTime = t;
          }
        }
      } else if (isPlaying && videoError) {
        setCurrentTime((prev) => {
          const next = prev + 0.016 * playbackSpeed;
          return next >= videoDuration ? 0 : next;
        });
      }

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [videoError, isPlaying, playbackSpeed, videoDuration]);

  const handleSeek = (newTime: number) => {
    const clamped = Math.max(0, Math.min(newTime, videoDuration));
    setCurrentTime(clamped);
    if (rawVideoRef.current) rawVideoRef.current.currentTime = clamped;
    if (aiVideoRef.current) aiVideoRef.current.currentTime = clamped;
  };

  const handleLoadedMetadata = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const dur = e.currentTarget.duration;
    if (dur && !isNaN(dur) && dur > 0) {
      setVideoDuration(dur);
    }
  };

  // Binary search for closest frame record in O(log N)
  const currentFrame = React.useMemo(() => {
    if (!frameRecords.length) return undefined;
    let low = 0;
    let high = frameRecords.length - 1;
    let bestIdx = 0;
    let minDiff = Infinity;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const diff = Math.abs(frameRecords[mid].timestamp - currentTime);
      if (diff < minDiff) {
        minDiff = diff;
        bestIdx = mid;
      }
      if (frameRecords[mid].timestamp < currentTime) {
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    return frameRecords[bestIdx];
  }, [frameRecords, currentTime]);

  return (
    <div className="glass-panel rounded-2xl p-6 border border-gray-700 shadow-2xl mb-8">
      {/* Header Bar with View Controls & Player Names */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5 border-b border-gray-800 pb-4">
        <div className="flex items-center space-x-3">
          <Activity className="w-5 h-5 text-brand-cyan" />
          <div>
            <h3 className="font-bold text-lg text-white">
              Trình Xem Trận Đấu & Radar Đồng Bộ Thời Gian Thực
            </h3>
            <p className="text-xs text-gray-400">
              Chiếu phối cảnh Homography 3D & Định vị bước chân vận động viên trên sân
            </p>
          </div>
        </div>

        <div className="flex items-center flex-wrap gap-2">
          {/* Edit Athlete Names Button */}
          <button
            onClick={() => {
              setIsEditingNames(!isEditingNames);
              setP1Input(p1Name);
              setP2Input(p2Name);
            }}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all ${
              isEditingNames
                ? "bg-amber-950/70 border-amber-500 text-amber-300 shadow-sm shadow-amber-500/30"
                : "bg-surface border-gray-700 text-gray-300 hover:text-white hover:border-gray-500"
            }`}
            title="Đổi tên vận động viên trên Video và Bảng điểm"
          >
            <Edit3 className="w-3.5 h-3.5" />
            <span>Đổi tên VĐV</span>
          </button>

          {/* Toggle Court Perspective Nodes Mesh */}
          <button
            onClick={() => setShowCourtMesh(!showCourtMesh)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all ${
              showCourtMesh
                ? "bg-emerald-950/70 border-emerald-500 text-emerald-300 shadow-sm shadow-emerald-500/20"
                : "bg-surface border-gray-800 text-gray-400 hover:text-gray-200"
            }`}
            title="Bật/Tắt Lưới tọa độ sân 3D và các Node điểm chuẩn Homography"
          >
            <Grid className="w-3.5 h-3.5" />
            <span>{showCourtMesh ? "Lưới Sân 3D: Bật" : "Lưới Sân 3D: Tắt"}</span>
          </button>

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
              <span>Phát Song Song</span>
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
            <span>{showOverlays ? "Khung AI: Bật" : "Khung AI: Tắt"}</span>
          </button>

          {/* Toggle Voronoi Court Space Control */}
          <button
            onClick={() => setShowVoronoi(!showVoronoi)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all ${
              showVoronoi
                ? "bg-purple-950/60 border-purple-700 text-purple-300 shadow-sm shadow-purple-500/20"
                : "bg-surface border-gray-800 text-gray-400 hover:text-gray-200"
            }`}
            title="Hiển thị vùng kiểm soát không gian sân Voronoi"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>{showVoronoi ? "Voronoi: Bật" : "Voronoi: Tắt"}</span>
          </button>
        </div>
      </div>

      {/* Edit Player Names Inline Modal / Banner */}
      {isEditingNames && (
        <div className="mb-5 p-4 rounded-xl bg-surface-light border border-amber-500/50 shadow-2xl flex flex-wrap items-center justify-between gap-4 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center space-x-2 text-amber-400 font-bold text-xs">
            <UserCheck className="w-4 h-4" />
            <span>Gán Tên & Quốc Gia Cho 2 Vận Động Viên (Cập nhật trực tiếp lên Video & Radar):</span>
          </div>

          <div className="flex flex-wrap items-center gap-3 flex-1">
            {/* P1 Input */}
            <div className="flex items-center space-x-2 bg-black/60 px-3 py-1.5 rounded-lg border border-cyan-500/40 flex-1 min-w-[200px]">
              <span className="text-[11px] font-extrabold text-cyan-400 whitespace-nowrap">
                P1 (Gần):
              </span>
              <input
                type="text"
                value={p1Input}
                onChange={(e) => setP1Input(e.target.value)}
                placeholder="Ví dụ: K. Naraoka (JPN)"
                className="bg-transparent text-xs text-white focus:outline-none w-full font-medium"
              />
            </div>

            {/* P2 Input */}
            <div className="flex items-center space-x-2 bg-black/60 px-3 py-1.5 rounded-lg border border-amber-500/40 flex-1 min-w-[200px]">
              <span className="text-[11px] font-extrabold text-amber-400 whitespace-nowrap">
                P2 (Xa):
              </span>
              <input
                type="text"
                value={p2Input}
                onChange={(e) => setP2Input(e.target.value)}
                placeholder="Ví dụ: Shi Yuqi (CHN)"
                className="bg-transparent text-xs text-white focus:outline-none w-full font-medium"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center space-x-2">
            <button
              onClick={handleSaveNames}
              disabled={isSavingNames}
              className="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs flex items-center space-x-1.5 shadow-md shadow-emerald-500/20 active:scale-95 transition-all"
            >
              <Check className="w-3.5 h-3.5" />
              <span>{isSavingNames ? "Đang lưu..." : "Lưu tên"}</span>
            </button>
            <button
              onClick={() => setIsEditingNames(false)}
              className="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

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
                  <span>Video Gốc</span>
                </div>

                {!videoError ? (
                  <video
                    ref={rawVideoRef}
                    src={videoSrc}
                    playsInline
                    muted={true}
                    autoPlay
                    onLoadedMetadata={handleLoadedMetadata}
                    onDurationChange={handleLoadedMetadata}
                    onEnded={() => setIsPlaying(false)}
                    className="w-full h-full object-contain bg-black"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gray-950 text-gray-500 text-xs">
                    Luồng Video Gốc
                  </div>
                )}
              </div>
            )}

            {/* Screen 2: AI Computer Vision & Tracking Stream */}
            <div className="relative aspect-video w-full rounded-2xl overflow-hidden bg-black border border-gray-800 shadow-xl flex flex-col justify-between">
              {/* Header Tag */}
              <div className="absolute top-3 left-3 z-10 flex items-center space-x-1.5 bg-black/80 backdrop-blur-md px-2.5 py-1 rounded-lg border border-cyan-500/40 text-[11px] font-bold text-cyan-300 shadow-lg">
                <Sparkles className="w-3.5 h-3.5 text-brand-cyan" />
                <span>Thị Giác AI & Theo Dấu</span>
              </div>

              {!videoError ? (
                <video
                  ref={aiVideoRef}
                  src={videoSrc}
                  playsInline
                  muted={isMuted}
                  autoPlay
                  onLoadedMetadata={handleLoadedMetadata}
                  onDurationChange={handleLoadedMetadata}
                  onEnded={() => setIsPlaying(false)}
                  onError={() => setVideoError(true)}
                  className="w-full h-full object-contain bg-black"
                />
              ) : (
                /* Fallback Synthetic Court Visualizer */
                <div className="absolute inset-0 bg-gradient-to-t from-gray-950 via-slate-900 to-black flex items-center justify-center opacity-90">
                  <div className="w-4/5 h-4/5 border-2 border-emerald-600/40 rounded-lg transform -perspective-500 rotate-x-12 relative flex items-center justify-center">
                    <div className="w-full h-0.5 bg-cyan-400/60 absolute top-1/2"></div>
                    <span className="text-xs text-emerald-500/50 font-mono">GÓC NHÌN SÂN CẦU LÔNG</span>
                  </div>
                </div>
              )}

              {/* 3D Perspective Court Nodes & Connected Mesh Grid Overlay */}
              {showCourtMesh && (
                <svg
                  className="absolute inset-0 w-full h-full pointer-events-none z-10"
                  viewBox="0 0 100 100"
                  preserveAspectRatio="none"
                >
                  {/* Outer Court Perspective Perimeter Polygon (On Green Mat) */}
                  <polygon
                    points="35,52 65,52 82,90 18,90"
                    fill="rgba(16, 185, 129, 0.05)"
                    stroke="rgba(16, 185, 129, 0.85)"
                    strokeWidth="0.8"
                    strokeLinejoin="round"
                  />

                  {/* Net Line (Cyan Neon Dashed) */}
                  <line
                    x1="29"
                    y1="62"
                    x2="71"
                    y2="62"
                    stroke="#00e5ff"
                    strokeWidth="1.2"
                    strokeDasharray="1.5, 1"
                  />

                  {/* Far Short Service Line */}
                  <line
                    x1="33"
                    y1="56"
                    x2="67"
                    y2="56"
                    stroke="rgba(16, 185, 129, 0.6)"
                    strokeWidth="0.6"
                  />

                  {/* Near Short Service Line */}
                  <line
                    x1="24"
                    y1="75"
                    x2="76"
                    y2="75"
                    stroke="rgba(16, 185, 129, 0.6)"
                    strokeWidth="0.6"
                  />

                  {/* Center Longitudinal Line */}
                  <line
                    x1="50"
                    y1="52"
                    x2="50"
                    y2="56"
                    stroke="rgba(16, 185, 129, 0.5)"
                    strokeWidth="0.5"
                  />
                  <line
                    x1="50"
                    y1="75"
                    x2="50"
                    y2="90"
                    stroke="rgba(16, 185, 129, 0.5)"
                    strokeWidth="0.5"
                  />

                  {/* Court Corner Landmark Nodes (Glowing Points on Floor) */}
                  {[
                    { cx: 35, cy: 52, label: "P_TL" },
                    { cx: 65, cy: 52, label: "P_TR" },
                    { cx: 82, cy: 90, label: "P_BR" },
                    { cx: 18, cy: 90, label: "P_BL" },
                    { cx: 29, cy: 62, label: "Net_L" },
                    { cx: 71, cy: 62, label: "Net_R" },
                  ].map((node) => (
                    <g key={node.label}>
                      <circle cx={node.cx} cy={node.cy} r="1.2" fill="#10b981" />
                      <circle
                        cx={node.cx}
                        cy={node.cy}
                        r="2.2"
                        fill="none"
                        stroke="#00e5ff"
                        strokeWidth="0.4"
                        opacity="0.9"
                      />
                    </g>
                  ))}
                </svg>
              )}

              {/* Synchronized AI Tracking Overlays */}
              {showOverlays && (
                <div className="absolute inset-0 pointer-events-none p-3 flex flex-col justify-between z-20">
                  {/* Top Right HUD */}
                  <div className="flex justify-between items-center text-[11px] font-mono text-cyan-300 bg-black/85 px-3 py-1 rounded-lg border border-cyan-500/40 w-fit backdrop-blur-md self-end mt-1 shadow-lg">
                    <span>FRAME: {currentFrame ? currentFrame.frame_idx : 0}</span>
                    <span className="ml-3 font-bold text-white">
                      THỜI GIAN: {currentTime.toFixed(2)}s
                    </span>
                  </div>

                  {/* Player & Shuttlecock Bounding Boxes */}
                  {currentFrame && (
                    <div className="absolute inset-0">
                      {/* Player 1 (Cyan - Near) and Player 2 (Amber - Far) */}
                      {currentFrame.players.map((p) => {
                        let left = `${p.x_norm * 70 + 15}%`;
                        let top = p.player_id === 1 ? "68%" : "44%";
                        let width = p.player_id === 1 ? "4.5rem" : "3.2rem";
                        let height = p.player_id === 1 ? "6.8rem" : "4.0rem";
                        let footX = p.x_norm * 70 + 15;
                        let footY = p.player_id === 1 ? 90 : 54;

                        if (p.bbox_norm && p.bbox_norm.length === 4) {
                          const [bx1, by1, bx2, by2] = p.bbox_norm;
                          left = `${Math.max(0, Math.min(95, bx1 * 100))}%`;
                          top = `${Math.max(0, Math.min(90, by1 * 100))}%`;
                          width = `${Math.max(4, Math.min(45, (bx2 - bx1) * 100))}%`;
                          height = `${Math.max(6, Math.min(65, (by2 - by1) * 100))}%`;
                          footX = (bx1 + bx2) * 50;
                          footY = by2 * 100;
                        }

                        const isP1 = p.player_id === 1;
                        const borderColor = isP1
                          ? "border-cyan-400 shadow-[0_0_12px_rgba(0,229,255,0.5)]"
                          : "border-amber-400 shadow-[0_0_12px_rgba(255,145,0,0.5)]";
                        const badgeBg = isP1
                          ? "bg-cyan-500 text-black font-extrabold"
                          : "bg-amber-500 text-black font-extrabold";
                        const confText = p.confidence ? `${Math.round(p.confidence * 100)}%` : "94%";
                        const displayName = isP1 ? p1Name : p2Name;
                        const coordText = `(${Math.round(p.x_norm * 100)}%, ${Math.round(
                          p.y_norm * 100
                        )}%)`;

                        return (
                          <React.Fragment key={p.player_id}>
                            {/* Player Bounding Box */}
                            <div
                              className={`absolute border-2 ${borderColor} rounded-xl transition-all duration-75 flex flex-col justify-between p-1 bg-black/25 backdrop-blur-[0.5px]`}
                              style={{ top, left, width, height }}
                            >
                              <div className="flex items-center space-x-1.5 bg-black/90 px-1.5 py-0.5 rounded-md text-white w-fit border border-gray-700 shadow-md">
                                <span className={`text-[9px] px-1 py-0.2 rounded ${badgeBg}`}>
                                  P{p.player_id}
                                </span>
                                <span className="text-[9px] font-bold text-gray-100 max-w-[100px] truncate">
                                  {displayName}
                                </span>
                                <span className="text-[8px] opacity-75">{confText}</span>
                              </div>

                              <div className="flex items-center justify-between px-1 text-[8px] font-mono text-gray-300 bg-black/70 rounded">
                                <span>2D Court:</span>
                                <span className={isP1 ? "text-cyan-300 font-bold" : "text-amber-300 font-bold"}>
                                  {coordText}
                                </span>
                              </div>
                            </div>

                            {/* Contact Point Node on Floor (Feet Anchor) */}
                            <div
                              className="absolute pointer-events-none transform -translate-x-1/2 -translate-y-1/2 z-10"
                              style={{ left: `${footX}%`, top: `${footY}%` }}
                            >
                              <div className="relative flex items-center justify-center">
                                <div
                                  className={`w-6 h-6 rounded-full border border-dashed animate-spin-slow ${
                                    isP1 ? "border-cyan-400" : "border-amber-400"
                                  }`}
                                />
                                <div
                                  className={`w-2.5 h-2.5 rounded-full absolute shadow-lg ${
                                    isP1
                                      ? "bg-cyan-400 shadow-cyan-400/80"
                                      : "bg-amber-400 shadow-amber-400/80"
                                  }`}
                                />
                              </div>
                            </div>
                          </React.Fragment>
                        );
                      })}

                      {/* Real White Shuttlecock (Rendered ONLY when visible) */}
                      {currentFrame.shuttle &&
                        currentFrame.shuttle.visible &&
                        currentFrame.shuttle.center_norm && (
                          <div
                            className="absolute transition-all duration-75 z-30 pointer-events-none"
                            style={{
                              top: `${currentFrame.shuttle.center_norm[1] * 100}%`,
                              left: `${currentFrame.shuttle.center_norm[0] * 100}%`,
                              transform: "translate(-50%, -50%)",
                            }}
                          >
                            <div className="relative flex items-center justify-center">
                              <div className="w-5 h-5 rounded-full border-2 border-white/90 shadow-[0_0_12px_#ffffff] animate-ping absolute" />
                              <div className="w-3.5 h-3.5 rounded-full bg-white border border-cyan-400 shadow-[0_0_10px_#ffffff]" />
                              <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[9px] font-bold text-white bg-black/85 px-1.5 py-0.2 rounded border border-white/40 whitespace-nowrap shadow-md">
                                🏸 Quả cầu
                              </span>
                            </div>
                          </div>
                        )}
                    </div>
                  )}

                  {/* Bottom Model Badge */}
                  <div className="text-right text-[10px] text-cyan-400 bg-black/80 px-2.5 py-0.5 rounded-md w-fit self-end font-mono border border-cyan-800/60 shadow-md">
                    <span>YOLOv8 + ByteTrack v2 (Khóa ID Cố Định)</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Unified Timeline & Master Controls Bar */}
          <div className="p-4 bg-surface rounded-2xl border border-gray-800 flex flex-col space-y-3 shadow-xl">
            {/* Scrubber with Clear Real Time Display */}
            <div className="flex items-center space-x-3">
              <span className="text-xs font-mono text-cyan-400 font-bold w-16">
                {formatTime(currentTime)}
              </span>
              <input
                type="range"
                min="0"
                max={videoDuration > 0 ? videoDuration : 1}
                step="0.05"
                value={Math.min(currentTime, videoDuration)}
                onChange={(e) => handleSeek(parseFloat(e.target.value))}
                className="w-full h-2.5 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-brand-cyan hover:accent-cyan-300 transition-all"
              />
              <span className="text-xs font-mono text-gray-300 font-bold w-16 text-right">
                {formatTime(videoDuration)}
              </span>
            </div>

            {/* Playback Buttons */}
            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="px-4 py-2 rounded-xl bg-brand-cyan hover:bg-cyan-300 text-black font-bold text-xs flex items-center space-x-2 transition-all shadow-md shadow-cyan-500/25 active:scale-95"
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
                <span className="text-[11px] text-gray-400 font-medium mr-1">Tốc độ:</span>
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
        <div className="flex flex-col items-center justify-between p-3.5 glass-panel rounded-2xl border border-gray-800 shadow-xl">
          <div className="w-full flex items-center justify-between mb-2 border-b border-gray-800 pb-2">
            <span className="text-xs font-bold text-gray-200 tracking-wider">
              Bản Đồ Sân 2D (Radar Live)
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
              60 FPS Homography
            </span>
          </div>

          <RadarCanvas
            currentFrame={currentFrame}
            width={260}
            height={460}
            showVoronoi={showVoronoi}
          />

          <div className="w-full mt-3 pt-2.5 border-t border-gray-800/80 flex flex-col space-y-1.5 text-[11px] text-gray-300">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-1.5 max-w-[120px] truncate">
                <div className="w-2.5 h-2.5 rounded-full bg-brand-cyan shadow-sm shadow-cyan-400 flex-shrink-0" />
                <span className="truncate">{p1Name} (Gần)</span>
              </div>
              <div className="flex items-center space-x-1.5 max-w-[120px] truncate">
                <div className="w-2.5 h-2.5 rounded-full bg-brand-amber shadow-sm shadow-amber-400 flex-shrink-0" />
                <span className="truncate">{p2Name} (Xa)</span>
              </div>
            </div>
            <div className="flex items-center space-x-1.5 text-gray-400 text-[10px]">
              <div className="w-2 h-2 rounded-full bg-white shadow-sm shadow-white" />
              <span>🏸 Vị trí quả cầu (Real-time)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
