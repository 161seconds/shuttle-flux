export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ProcessingStatus {
  match_id: string;
  status: "queued" | "processing" | "completed" | "failed" | "cancelled";
  progress_percentage: number;
  current_stage: string;
  error_message?: string;
}

export interface RuntimeComponent {
  available: boolean;
  active: boolean;
  enabled?: boolean;
  version?: string | null;
  device?: string | null;
  engine?: string;
  providers?: string[];
  model_path?: string;
  mode?: string;
  path?: string;
  service_url?: string | null;
}

export interface RuntimeStatus {
  selected_backend: string;
  inference_mode: "local" | "remote";
  components: Record<string, RuntimeComponent>;
  inference_service?: {
    configured: boolean;
    reachable: boolean;
    url?: string | null;
    runtime?: RuntimeStatus;
    error?: string;
  };
}

export interface PlayerStatsData {
  player_id: number;
  label: string;
  side: string;
  distance_meters: number;
  avg_speed_mps: number;
  max_speed_mps: number;
  active_time_seconds: number;
  court_control_pct?: number;
  zone_occupancy: Record<string, number>;
}

export interface RallyData {
  rally_id: number;
  name: string;
  start_frame: number;
  end_frame: number;
  start_time: number;
  end_time: number;
  duration_seconds: number;
  estimated_shot_count: number;
  confidence: number;
}

export interface FrameRecord {
  frame_idx: number;
  timestamp: number;
  players: Array<{
    player_id: number;
    label?: string;
    x_norm: number;
    y_norm: number;
    bbox?: number[];
    bbox_norm?: [number, number, number, number];
    confidence?: number;
    pose?: {
      source?: string;
      keypoints: Record<string, [number, number, number]>;
      angles?: Record<string, number>;
    };
  }>;
  rackets?: Array<{
    owner_id?: number;
    bbox_norm?: [number, number, number, number];
    center_norm?: [number, number];
    confidence?: number;
    source?: string;
    orientation_degrees?: number;
    speed_px_per_frame?: number;
    keypoints_norm?: Record<string, [number, number, number]>;
  }>;
  shuttle?: {
    x_norm: number;
    y_norm: number;
    center_norm?: [number, number];
    visible: boolean;
    confidence?: number;
  };
}

export interface HitItem {
  hit_index: number;
  timestamp: number;
  player_id: number;
  shot_type: string;
  confidence: number;
}

export interface CourtCalibrationData {
  source: string;
  confidence: number;
  detected_line_count: number;
  initial_detected_line_count?: number;
  reprojection_error_norm?: number | null;
  used_fallback: boolean;
  line_scores?: Record<string, number>;
}

export interface MatchAnalytics {
  metadata: {
    match_id: string;
    fps: number;
    total_frames: number;
    duration_seconds: number;
    mode: string;
    is_doubles?: boolean;
  };
  overview: {
    total_rallies: number;
    total_shots: number;
    active_play_duration_sec: number;
    total_distance_player_1_m: number;
    total_distance_player_2_m: number;
    total_distance_player_3_m?: number;
    total_distance_player_4_m?: number;
    court_control?: {
      player_1_control_pct: number;
      player_2_control_pct: number;
    };
  };
  players: {
    player_1: PlayerStatsData;
    player_2: PlayerStatsData;
    player_3?: PlayerStatsData;
    player_4?: PlayerStatsData;
  };
  rallies: RallyData[];
  hits: HitItem[];
  heatmaps?: Record<string, any>;
  court_nodes?: Record<string, [number, number]>;
  court_lines?: Record<string, [[number, number], [number, number]]>;
  court_calibration?: CourtCalibrationData;
  scoreboard?: Record<string, any>;
  frame_records?: FrameRecord[];
}

export type MatchAnalyticsPayload = Omit<
  Partial<MatchAnalytics>,
  "metadata" | "overview" | "players"
> & {
  metadata?: Partial<MatchAnalytics["metadata"]>;
  overview?: Partial<MatchAnalytics["overview"]>;
  players?: {
    player_1?: Partial<PlayerStatsData>;
    player_2?: Partial<PlayerStatsData>;
    player_3?: Partial<PlayerStatsData>;
    player_4?: Partial<PlayerStatsData>;
  };
};

function createEmptyPlayer(playerId: number, label: string, side: string): PlayerStatsData {
  return {
    player_id: playerId,
    label,
    side,
    distance_meters: 0,
    avg_speed_mps: 0,
    max_speed_mps: 0,
    active_time_seconds: 0,
    court_control_pct: 50,
    zone_occupancy: {},
  };
}

export function createEmptyMatchAnalytics(matchId: string): MatchAnalytics {
  return {
    metadata: {
      match_id: matchId,
      fps: 30,
      total_frames: 0,
      duration_seconds: 0,
      mode: "Singles 1v1",
    },
    overview: {
      total_rallies: 0,
      total_shots: 0,
      active_play_duration_sec: 0,
      total_distance_player_1_m: 0,
      total_distance_player_2_m: 0,
    },
    players: {
      player_1: createEmptyPlayer(1, "Player 1 (Near)", "Near Court"),
      player_2: createEmptyPlayer(2, "Player 2 (Far)", "Far Court"),
    },
    rallies: [],
    hits: [],
    heatmaps: {},
    frame_records: [],
  };
}

export function mergeMatchAnalytics(
  current: MatchAnalytics | null,
  incoming: MatchAnalyticsPayload,
  matchId: string
): MatchAnalytics {
  const base = current ?? createEmptyMatchAnalytics(matchId);
  const incomingPlayers = incoming.players ?? {};
  const players: MatchAnalytics["players"] = {
    player_1: { ...base.players.player_1, ...incomingPlayers.player_1 },
    player_2: { ...base.players.player_2, ...incomingPlayers.player_2 },
  };

  const player3 = incomingPlayers.player_3
    ? { ...(base.players.player_3 ?? createEmptyPlayer(3, "Player 3", "Near Court")), ...incomingPlayers.player_3 }
    : base.players.player_3;
  const player4 = incomingPlayers.player_4
    ? { ...(base.players.player_4 ?? createEmptyPlayer(4, "Player 4", "Far Court")), ...incomingPlayers.player_4 }
    : base.players.player_4;
  if (player3) players.player_3 = player3;
  if (player4) players.player_4 = player4;

  return {
    metadata: { ...base.metadata, ...incoming.metadata, match_id: incoming.metadata?.match_id ?? matchId },
    overview: { ...base.overview, ...incoming.overview },
    players,
    rallies: Array.isArray(incoming.rallies) ? incoming.rallies : base.rallies,
    hits: Array.isArray(incoming.hits) ? incoming.hits : base.hits,
    heatmaps: incoming.heatmaps ?? base.heatmaps,
    court_nodes: incoming.court_nodes ?? base.court_nodes,
    court_lines: incoming.court_lines ?? base.court_lines,
    court_calibration: incoming.court_calibration ?? base.court_calibration,
    scoreboard: incoming.scoreboard ?? base.scoreboard,
    frame_records: Array.isArray(incoming.frame_records)
      ? incoming.frame_records
      : base.frame_records,
  };
}

export async function uploadVideo(file: File): Promise<{ match_id: string; status: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/api/v1/matches/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Upload failed");
  }

  return res.json();
}

export async function getProcessingStatus(matchId: string): Promise<ProcessingStatus> {
  const res = await fetch(`${API_BASE_URL}/api/v1/matches/${matchId}/processing`);
  if (!res.ok) {
    throw new Error("Failed to fetch processing status");
  }
  return res.json();
}

export async function getRuntimeStatus(): Promise<RuntimeStatus> {
  const res = await fetch(`${API_BASE_URL}/api/v1/runtime`, {
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) {
    throw new Error("Failed to fetch runtime status");
  }
  return res.json();
}
export async function getMatchAnalytics(matchId: string): Promise<MatchAnalyticsPayload> {
  const res = await fetch(`${API_BASE_URL}/api/v1/matches/${matchId}/analytics`);
  if (!res.ok) {
    throw new Error("Failed to fetch match analytics");
  }
  return res.json();
}

export async function createDemoMatch(): Promise<{ match_id: string; analytics: MatchAnalytics }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/matches/demo`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error("Failed to create demo match");
  }
  return res.json();
}

export async function analyzeYouTubeUrl(url: string): Promise<{ match_id: string; status: string }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/matches/youtube`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url }),
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to analyze YouTube video");
  }

  return res.json();
}

export async function cancelProcessing(matchId: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/matches/${matchId}/cancel`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error("Failed to cancel match processing");
  }
  return res.json();
}

export async function updatePlayerNames(
  matchId: string,
  p1Name: string,
  p2Name: string
): Promise<{ status: string; analytics: MatchAnalytics }> {
  const res = await fetch(`${API_BASE_URL}/api/v1/matches/${matchId}/players`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ player_1_name: p1Name, player_2_name: p2Name }),
  });
  if (!res.ok) {
    throw new Error("Failed to update player names");
  }
  return res.json();
}
