"use client";

import React, { useState, useEffect } from "react";
import { Navbar } from "../components/Navbar";
import { UploadSection } from "../components/UploadSection";
import { OverviewCards } from "../components/OverviewCards";
import { VideoPlayerWithRadar } from "../components/VideoPlayerWithRadar";
import { PlayerStats } from "../components/PlayerStats";
import { HeatmapViewer } from "../components/HeatmapViewer";
import { RallyTimeline } from "../components/RallyTimeline";
import {
  MatchAnalytics,
  ProcessingStatus,
  uploadVideo,
  analyzeYouTubeUrl,
  cancelProcessing,
  getProcessingStatus,
  getMatchAnalytics,
  createDemoMatch,
  createEmptyMatchAnalytics,
  mergeMatchAnalytics,
} from "../lib/api";

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

export default function Home() {
  const [analytics, setAnalytics] = useState<MatchAnalytics | null>(null);
  const [activeMatchId, setActiveMatchId] = useState<string | null>(null);
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingDemo, setIsLoadingDemo] = useState(false);
  const [selectedRallyTime, setSelectedRallyTime] = useState<number | null>(null);

  // Poll processing progress & live frame streaming if active
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;
    let pollInFlight = false;

    if (activeMatchId && (!processingStatus || processingStatus.status === "processing")) {
      timer = setInterval(async () => {
        if (cancelled || pollInFlight) return;
        pollInFlight = true;
        try {
          const status = await getProcessingStatus(activeMatchId);
          if (cancelled) return;
          setProcessingStatus(status);

          // Stream live partial analytics as soon as frames are processed
          if (status.status === "processing") {
            try {
              const liveData = await getMatchAnalytics(activeMatchId);
              if (cancelled) return;
              if (liveData && liveData.frame_records && liveData.frame_records.length > 0) {
                setAnalytics((prev) => mergeMatchAnalytics(prev, liveData, activeMatchId));
              }
            } catch (_) {
              // Still preparing first batch — ignore 404
            }
          }

          if (status.status === "completed") {
            // Fetch final analytics and STOP polling
            cancelled = true;
            if (timer) clearInterval(timer);
            try {
              const data = await getMatchAnalytics(activeMatchId);
              setAnalytics((prev) => mergeMatchAnalytics(prev, data, activeMatchId));
            } catch (_) {}
          } else if (status.status === "failed" || status.status === "cancelled") {
            cancelled = true;
            if (timer) clearInterval(timer);
            if (status.status === "failed") {
              alert(`Xử lý video thất bại: ${status.error_message || "Lỗi không xác định"}`);
            }
            setActiveMatchId(null);
            setProcessingStatus(null);
          }
        } catch (e) {
          console.error("Polling error:", e);
        } finally {
          pollInFlight = false;
        }
      }, 2000); // Poll every 2s instead of 1s to reduce server load
    }
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [activeMatchId, processingStatus?.status]);

  const handleFileUpload = async (file: File) => {
    try {
      setIsUploading(true);
      const res = await uploadVideo(file);
      setActiveMatchId(res.match_id);
      setProcessingStatus({
        match_id: res.match_id,
        status: "processing",
        progress_percentage: 15,
        current_stage: "preprocessing",
      });

      setAnalytics(createEmptyMatchAnalytics(res.match_id));
    } catch (err: unknown) {
      alert(`Lỗi tải tệp: ${getErrorMessage(err)}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleYouTubeSubmit = async (url: string) => {
    try {
      setIsUploading(true);
      const res = await analyzeYouTubeUrl(url);
      setActiveMatchId(res.match_id);
      setProcessingStatus({
        match_id: res.match_id,
        status: "processing",
        progress_percentage: 5,
        current_stage: "downloading_youtube",
      });
    } catch (err: unknown) {
      alert(`Lỗi xử lý link YouTube: ${getErrorMessage(err)}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleCancelProcessing = async () => {
    if (activeMatchId) {
      try {
        await cancelProcessing(activeMatchId);
      } catch (e) {
        console.warn("Cancel warning:", e);
      }
    }
    setActiveMatchId(null);
    setProcessingStatus(null);
    setIsUploading(false);
  };

  const handleLoadDemo = async () => {
    try {
      setIsLoadingDemo(true);
      const res = await createDemoMatch();
      setActiveMatchId(res.match_id);
      setAnalytics(mergeMatchAnalytics(null, res.analytics, res.match_id));
      setProcessingStatus(null);
    } catch (err: any) {
      // If backend API server is offline, fallback to built-in client demo mock
      const fallbackDemo = generateClientDemoMock();
      setActiveMatchId("demo-local");
      setAnalytics(fallbackDemo);
      setProcessingStatus(null);
    } finally {
      setIsLoadingDemo(false);
    }
  };

  const handleReset = () => {
    setActiveMatchId(null);
    setAnalytics(null);
    setProcessingStatus(null);
    setSelectedRallyTime(null);
  };

  return (
    <div className="min-h-screen bg-background text-gray-100 flex flex-col justify-between">
      <Navbar
        onLoadDemo={handleLoadDemo}
        isLoadingDemo={isLoadingDemo}
        activeMatchId={activeMatchId}
        onReset={handleReset}
      />

      <main className="container mx-auto px-4 py-6 flex-1">
        {!analytics ? (
          <UploadSection
            onFileUpload={handleFileUpload}
            onYouTubeSubmit={handleYouTubeSubmit}
            onCancel={handleCancelProcessing}
            onLoadDemo={handleLoadDemo}
            isLoadingDemo={isLoadingDemo}
            processingStatus={processingStatus}
            isUploading={isUploading}
          />
        ) : (
          <div className="space-y-6">
            <OverviewCards analytics={analytics} />

            <VideoPlayerWithRadar
              analytics={analytics}
              selectedRallyTime={selectedRallyTime}
              processingStatus={processingStatus}
            />

            <RallyTimeline
              rallies={analytics.rallies}
              hits={analytics.hits}
              onSelectRally={(time) => setSelectedRallyTime(time)}
            />

            <PlayerStats analytics={analytics} />

            <HeatmapViewer analytics={analytics} />
          </div>
        )}
      </main>

      <footer className="glass-panel border-t border-gray-800 py-6 text-center text-xs text-gray-500">
        <p>Shuttle Flux — End-to-End Badminton AI Computer Vision & Analytics Platform</p>
      </footer>
    </div>
  );
}

// Built-in client fallback mock if backend is offline
function generateClientDemoMock(): MatchAnalytics {
  const frame_records = [];
  for (let f = 0; f < 600; f += 2) {
    const t = f / 30.0;
    // P1 (Near Player - Cyan): Bottom half of 2D court (y in 0.65 - 0.88)
    const p1_x = 0.5 + 0.2 * Math.sin(t * 1.5);
    const p1_y = 0.75 + 0.12 * Math.cos(t * 1.2);

    // P2 (Far Player - Amber): Top half of 2D court across net (y in 0.15 - 0.35)
    const p2_x = 0.5 - 0.22 * Math.sin(t * 1.4);
    const p2_y = 0.25 + 0.1 * Math.cos(t * 1.1);

    const shuttle_x = 0.5 + 0.25 * Math.cos(t * 2.5);
    const shuttle_y = 0.5 + 0.35 * Math.sin(t * 2.8);

    const p1_bx1 = Math.max(0.05, p1_x - 0.06);
    const p1_bx2 = Math.min(0.95, p1_x + 0.06);
    const p2_bx1 = Math.max(0.05, p2_x - 0.04);
    const p2_bx2 = Math.min(0.95, p2_x + 0.04);

    frame_records.push({
      frame_idx: f,
      timestamp: parseFloat(t.toFixed(2)),
      players: [
        {
          player_id: 1,
          label: "Player 1 (Viktor A.)",
          x_norm: parseFloat(p1_x.toFixed(3)),
          y_norm: parseFloat(p1_y.toFixed(3)),
          bbox_norm: [parseFloat(p1_bx1.toFixed(3)), 0.65, parseFloat(p1_bx2.toFixed(3)), 0.90] as [number, number, number, number],
          confidence: 0.95,
        },
        {
          player_id: 2,
          label: "Player 2 (Shi Y.)",
          x_norm: parseFloat(p2_x.toFixed(3)),
          y_norm: parseFloat(p2_y.toFixed(3)),
          bbox_norm: [parseFloat(p2_bx1.toFixed(3)), 0.42, parseFloat(p2_bx2.toFixed(3)), 0.55] as [number, number, number, number],
          confidence: 0.93,
        },
      ],
      shuttle: {
        x_norm: parseFloat(shuttle_x.toFixed(3)),
        y_norm: parseFloat(shuttle_y.toFixed(3)),
        center_norm: [parseFloat(shuttle_x.toFixed(3)), parseFloat((0.48 + 0.35 * (shuttle_y - 0.5)).toFixed(3))] as [number, number],
        visible: true,
        confidence: 0.90,
      },
    });
  }

  return {
    metadata: {
      match_id: "demo-client",
      fps: 30.0,
      total_frames: 600,
      duration_seconds: 20.0,
      mode: "Singles (BWF Standard)",
    },
    overview: {
      total_rallies: 3,
      total_shots: 14,
      active_play_duration_sec: 17.5,
      total_distance_player_1_m: 68.4,
      total_distance_player_2_m: 74.2,
    },
    players: {
      player_1: {
        player_id: 1,
        label: "Player 1 (Viktor A.)",
        side: "Near Court (Bottom)",
        distance_meters: 68.4,
        avg_speed_mps: 3.2,
        max_speed_mps: 7.1,
        active_time_seconds: 16.5,
        zone_occupancy: {
          P1_rear_left: 28.5,
          P1_rear_right: 22.1,
          P1_mid_left: 18.2,
          P1_mid_right: 15.0,
          P1_front_left: 9.2,
          P1_front_right: 7.0,
        },
      },
      player_2: {
        player_id: 2,
        label: "Player 2 (Shi Y.)",
        side: "Far Court (Top)",
        distance_meters: 74.2,
        avg_speed_mps: 3.5,
        max_speed_mps: 7.4,
        active_time_seconds: 17.0,
        zone_occupancy: {
          P2_rear_left: 24.0,
          P2_rear_right: 29.5,
          P2_mid_left: 19.5,
          P2_mid_right: 14.0,
          P2_front_left: 7.0,
          P2_front_right: 6.0,
        },
      },
    },
    rallies: [
      {
        rally_id: 1,
        name: "Rally #1 - Opening Exchange",
        start_frame: 30,
        end_frame: 180,
        start_time: 1.0,
        end_time: 6.0,
        duration_seconds: 5.0,
        estimated_shot_count: 4,
        confidence: 0.94,
      },
      {
        rally_id: 2,
        name: "Rally #2 - Fast Net Play & Smash",
        start_frame: 240,
        end_frame: 450,
        start_time: 8.0,
        end_time: 15.0,
        duration_seconds: 7.0,
        estimated_shot_count: 6,
        confidence: 0.91,
      },
      {
        rally_id: 3,
        name: "Rally #3 - Rear Court Battle",
        start_frame: 480,
        end_frame: 580,
        start_time: 16.0,
        end_time: 19.3,
        duration_seconds: 3.3,
        estimated_shot_count: 3,
        confidence: 0.88,
      },
    ],
    hits: [
      { hit_index: 1, timestamp: 1.2, player_id: 1, shot_type: "serve", confidence: 0.95 },
      { hit_index: 2, timestamp: 2.5, player_id: 2, shot_type: "clear", confidence: 0.88 },
      { hit_index: 3, timestamp: 4.1, player_id: 1, shot_type: "smash", confidence: 0.92 },
    ],
    frame_records,
  };
}
