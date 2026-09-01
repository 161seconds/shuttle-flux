import React, { useState, useRef } from "react";
import { UploadCloud, Film, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { ProcessingStatus } from "../lib/api";

interface UploadSectionProps {
  onFileUpload: (file: File) => void;
  processingStatus: ProcessingStatus | null;
  isUploading: boolean;
}

export const UploadSection: React.FC<UploadSectionProps> = ({
  onFileUpload,
  processingStatus,
  isUploading,
}) => {
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

  const stages = [
    { key: "preprocessing", label: "Video Ingestion & Metadata" },
    { key: "court_calibration", label: "Court Landmarks & Homography" },
    { key: "detection_and_tracking", label: "Player & Shuttlecock Tracking" },
    { key: "analytics", label: "Movement & Rally Analytics" },
    { key: "completed", label: "Rendering & Dashboard Ready" },
  ];

  return (
    <div className="max-w-4xl mx-auto py-12 px-4">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-extrabold text-white tracking-tight sm:text-4xl">
          Analyze Your Badminton Match with AI
        </h2>
        <p className="mt-3 text-lg text-gray-400 max-w-2xl mx-auto">
          Upload match footage to extract 2D court trajectories, player speed profiles, heatmaps, and rally breakdowns.
        </p>
      </div>

      {!processingStatus ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition-all duration-200 glass-panel ${
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
          <div className="mx-auto w-16 h-16 rounded-full bg-surface-light flex items-center justify-center mb-4 text-brand-cyan shadow-inner">
            <UploadCloud className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-semibold text-white">Drag & drop your badminton video here</h3>
          <p className="text-sm text-gray-400 mt-1">or click to browse from your device</p>
          <div className="mt-4 flex items-center justify-center space-x-3 text-xs text-gray-500">
            <span>Supports MP4, MOV, AVI</span>
            <span>•</span>
            <span>Up to 1080p 60fps recommended</span>
          </div>
        </div>
      ) : (
        <div className="glass-panel rounded-2xl p-8 border border-gray-700 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-3">
              <Film className="w-6 h-6 text-brand-cyan animate-pulse" />
              <div>
                <h3 className="font-bold text-white">Processing Match: {processingStatus.match_id}</h3>
                <p className="text-xs text-gray-400">Current stage: {processingStatus.current_stage}</p>
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
                processingStatus.progress_percentage >= (idx + 1) * 20;

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
