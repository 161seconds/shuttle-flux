import React, { useState, useRef } from "react";
import {
  UploadCloud,
  Film,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Youtube,
  Link as LinkIcon,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { ProcessingStatus } from "../lib/api";

interface UploadSectionProps {
  onFileUpload: (file: File) => void;
  onYouTubeSubmit: (url: string) => void;
  processingStatus: ProcessingStatus | null;
  isUploading: boolean;
}

export const UploadSection: React.FC<UploadSectionProps> = ({
  onFileUpload,
  onYouTubeSubmit,
  processingStatus,
  isUploading,
}) => {
  const [activeTab, setActiveTab] = useState<"youtube" | "file">("youtube");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [urlError, setUrlError] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileUpload(e.target.files[0]);
    }
  };

  const handleYoutubeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const url = youtubeUrl.trim();
    if (!url) {
      setUrlError("Vui lòng nhập link video YouTube.");
      return;
    }
    if (!url.includes("youtube.com") && !url.includes("youtu.be")) {
      setUrlError("Link không hợp lệ. Vui lòng nhập link từ youtube.com hoặc youtu.be");
      return;
    }
    setUrlError("");
    onYouTubeSubmit(url);
  };

  const stages = [
    { key: "downloading_youtube", label: "Downloading YouTube Video Stream" },
    { key: "preprocessing", label: "Video Ingestion & Frame Normalization" },
    { key: "court_calibration", label: "Court Landmarks & Homography Calibration" },
    { key: "detection_and_tracking", label: "Player & Shuttlecock AI Tracking" },
    { key: "analytics", label: "Movement & Rally Analytics Computation" },
    { key: "completed", label: "Rendering & Dashboard Ready" },
  ];

  return (
    <div className="max-w-4xl mx-auto py-12 px-4">
      <div className="text-center mb-8">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-cyan-950/60 border border-cyan-800 text-cyan-400 text-xs font-semibold mb-4">
          <Sparkles className="w-3.5 h-3.5" />
          <span>AI-Powered Badminton Match Analytics</span>
        </div>
        <h2 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl">
          Analyze Your Badminton Match with AI
        </h2>
        <p className="mt-3 text-base text-gray-400 max-w-2xl mx-auto">
          Paste a YouTube match link or upload video footage to extract 2D court trajectories, player speed profiles, heatmaps, and rally breakdowns.
        </p>
      </div>

      {!processingStatus ? (
        <div className="glass-panel rounded-2xl p-6 border border-gray-700 shadow-2xl">
          {/* Tab Selector */}
          <div className="flex border-b border-gray-800 mb-6">
            <button
              onClick={() => setActiveTab("youtube")}
              className={`flex items-center space-x-2 py-3 px-6 font-semibold text-sm transition-all border-b-2 ${
                activeTab === "youtube"
                  ? "border-red-500 text-white bg-red-950/20"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              <Youtube className="w-4 h-4 text-red-500" />
              <span>Paste YouTube Link</span>
            </button>
            <button
              onClick={() => setActiveTab("file")}
              className={`flex items-center space-x-2 py-3 px-6 font-semibold text-sm transition-all border-b-2 ${
                activeTab === "file"
                  ? "border-brand-cyan text-white bg-cyan-950/20"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              <UploadCloud className="w-4 h-4 text-brand-cyan" />
              <span>Upload Video File</span>
            </button>
          </div>

          {activeTab === "youtube" ? (
            <div className="py-4">
              <form onSubmit={handleYoutubeSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium uppercase tracking-wider text-gray-400 mb-2">
                    YouTube Video URL
                  </label>
                  <div className="flex flex-col sm:flex-row gap-3">
                    <div className="relative flex-1">
                      <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
                        <LinkIcon className="w-4 h-4" />
                      </div>
                      <input
                        type="text"
                        value={youtubeUrl}
                        onChange={(e) => {
                          setYoutubeUrl(e.target.value);
                          setUrlError("");
                        }}
                        placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/..."
                        className="w-full pl-10 pr-4 py-3 bg-surface border border-gray-700 focus:border-red-500 focus:ring-1 focus:ring-red-500 rounded-xl text-sm text-white placeholder-gray-500 transition-all outline-none"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={isUploading}
                      className="px-6 py-3 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-bold text-sm rounded-xl shadow-lg shadow-red-600/30 flex items-center justify-center space-x-2 transition-all duration-200 disabled:opacity-50"
                    >
                      {isUploading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <span>Fetch & Analyze</span>
                          <ArrowRight className="w-4 h-4" />
                        </>
                      )}
                    </button>
                  </div>
                  {urlError && <p className="text-xs text-rose-400 mt-2">{urlError}</p>}
                </div>

                <div className="flex flex-wrap items-center justify-between text-xs text-gray-500 pt-3 border-t border-gray-800/80">
                  <div className="flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                    <span>Supports all standard YouTube videos & Shorts</span>
                  </div>
                  <span className="text-gray-400">Stream download powered by yt-dlp</span>
                </div>
              </form>
            </div>
          ) : (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-200 ${
                isDragOver
                  ? "border-brand-cyan bg-cyan-950/20 scale-[1.01]"
                  : "border-gray-700 hover:border-gray-500 hover:bg-surface"
              }`}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept="video/mp4,video/quicktime,video/x-msvideo"
                className="hidden"
              />
              <div className="mx-auto w-14 h-14 rounded-full bg-surface-light flex items-center justify-center mb-3 text-brand-cyan shadow-inner">
                <UploadCloud className="w-7 h-7" />
              </div>
              <h3 className="text-base font-semibold text-white">Drag & drop your badminton video here</h3>
              <p className="text-xs text-gray-400 mt-1">or click to browse from your computer</p>
              <div className="mt-4 flex items-center justify-center space-x-3 text-[11px] text-gray-500">
                <span>MP4, MOV, AVI</span>
                <span>•</span>
                <span>Up to 1080p 60fps recommended</span>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="glass-panel rounded-2xl p-8 border border-gray-700 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-3">
              <Film className="w-6 h-6 text-brand-cyan animate-pulse" />
              <div>
                <h3 className="font-bold text-white">Processing Match: {processingStatus.match_id}</h3>
                <p className="text-xs text-gray-400">
                  Current stage:{" "}
                  <span className="text-cyan-300 font-medium">
                    {stages.find((s) => s.key === processingStatus.current_stage)?.label ||
                      processingStatus.current_stage}
                  </span>
                </p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-2xl font-black text-brand-cyan">
                {processingStatus.progress_percentage}%
              </span>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="w-full h-3 bg-surface-light rounded-full overflow-hidden mb-6 p-0.5 border border-gray-700">
            <div
              className="h-full bg-gradient-to-r from-brand-cyan via-cyan-400 to-brand-amber rounded-full transition-all duration-500 shadow-lg shadow-cyan-500/50"
              style={{ width: `${Math.max(5, processingStatus.progress_percentage)}%` }}
            ></div>
          </div>

          {/* Stage items */}
          <div className="space-y-3 pt-2">
            {stages.map((st, idx) => {
              const isCurrent = processingStatus.current_stage === st.key;
              const isPast =
                processingStatus.status === "completed" ||
                processingStatus.progress_percentage >= (idx + 1) * (100 / stages.length);

              return (
                <div
                  key={st.key}
                  className={`flex items-center justify-between text-sm p-2.5 rounded-lg transition-colors ${
                    isCurrent
                      ? "bg-cyan-950/40 text-cyan-300 border border-cyan-800/60"
                      : isPast
                      ? "text-gray-300"
                      : "text-gray-600"
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    {isPast ? (
                      <CheckCircle2 className="w-4 h-4 text-brand-green" />
                    ) : isCurrent ? (
                      <Loader2 className="w-4 h-4 text-brand-cyan animate-spin" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-gray-700"></div>
                    )}
                    <span>{st.label}</span>
                  </div>
                  {isCurrent && <span className="text-xs font-semibold uppercase tracking-wider">In Progress</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
