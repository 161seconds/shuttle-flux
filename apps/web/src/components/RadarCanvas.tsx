import React, { useRef, useEffect } from "react";
import { FrameRecord } from "../lib/api";

interface RadarCanvasProps {
  currentFrame?: FrameRecord;
  width?: number;
  height?: number;
  showVoronoi?: boolean;
}

const SINGLES_PAD = 0.46 / 6.1;
const DOUBLES_LONG_FAR = 0.76 / 13.4;
const SHORT_FAR = (6.7 - 1.98) / 13.4;
const NET_Y = 0.5;
const SHORT_NEAR = (6.7 + 1.98) / 13.4;
const DOUBLES_LONG_NEAR = 1 - DOUBLES_LONG_FAR;

export const RadarCanvas: React.FC<RadarCanvasProps> = ({
  currentFrame,
  width = 280,
  height = 500,
  showVoronoi = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const shuttleTrailRef = useRef<Array<{ x: number; y: number }>>([]);
  const lastShuttleFrameRef = useRef<number | null>(null);
  const pulsePhaseRef = useRef<number>(0);

  useEffect(() => {
    let animId: number;

    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      pulsePhaseRef.current += 0.05;
      const pulse = Math.sin(pulsePhaseRef.current);

      // Deep dark background
      ctx.fillStyle = "#0c1017";
      ctx.fillRect(0, 0, width, height);

      const pad = 24;
      const courtW = width - 2 * pad;
      const courtH = height - 2 * pad;
      const x0 = pad;
      const y0 = pad;
      const x1 = pad + courtW;
      const y1 = pad + courtH;

      // Court Floor with subtle gradient
      const courtGrad = ctx.createLinearGradient(0, y0, 0, y1);
      courtGrad.addColorStop(0, "#131b26");
      courtGrad.addColorStop(0.5, "#182333");
      courtGrad.addColorStop(1, "#131b26");
      ctx.fillStyle = courtGrad;
      ctx.fillRect(x0, y0, courtW, courtH);

      // Voronoi Court Control Shading (if enabled)
      if (showVoronoi && currentFrame && currentFrame.players && currentFrame.players.length >= 2) {
        const p1 = currentFrame.players.find((p) => p.player_id === 1);
        const p2 = currentFrame.players.find((p) => p.player_id === 2);
        if (p1 && p2) {
          const p1x = x0 + Math.max(0.05, Math.min(0.95, p1.x_norm)) * courtW;
          const p1y = y0 + Math.max(0.05, Math.min(0.95, p1.y_norm)) * courtH;
          const p2x = x0 + Math.max(0.05, Math.min(0.95, p2.x_norm)) * courtW;
          const p2y = y0 + Math.max(0.05, Math.min(0.95, p2.y_norm)) * courtH;

          ctx.save();
          ctx.beginPath();
          ctx.rect(x0, y0, courtW, courtH);
          ctx.clip();

          // P1 Dominance Gradient
          const g1 = ctx.createRadialGradient(p1x, p1y, 10, p1x, p1y, courtH * 0.7);
          g1.addColorStop(0, "rgba(0, 229, 255, 0.28)");
          g1.addColorStop(1, "rgba(0, 229, 255, 0.02)");
          ctx.fillStyle = g1;
          ctx.fillRect(x0, y0, courtW, courtH);

          // P2 Dominance Gradient
          const g2 = ctx.createRadialGradient(p2x, p2y, 10, p2x, p2y, courtH * 0.7);
          g2.addColorStop(0, "rgba(255, 145, 0, 0.28)");
          g2.addColorStop(1, "rgba(255, 145, 0, 0.02)");
          ctx.fillStyle = g2;
          ctx.fillRect(x0, y0, courtW, courtH);

          ctx.restore();
        }
      }

      // Court Outer Boundary
      ctx.strokeStyle = "#374151";
      ctx.lineWidth = 2;
      ctx.strokeRect(x0, y0, courtW, courtH);

      // BWF singles sidelines sit 0.46m inside the 6.10m doubles court.
      const singlesPad = courtW * SINGLES_PAD;
      ctx.strokeStyle = "#1f2937";
      ctx.lineWidth = 1;
      ctx.strokeRect(x0 + singlesPad, y0, courtW - 2 * singlesPad, courtH);

      // Net Line (y = 0.5) with cyan neon glow
      const netY = y0 + NET_Y * courtH;
      ctx.shadowColor = "#00e5ff";
      ctx.shadowBlur = 8;
      ctx.strokeStyle = "#00e5ff";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(x0 - 6, netY);
      ctx.lineTo(x1 + 6, netY);
      ctx.stroke();
      ctx.shadowBlur = 0; // Reset shadow

      // Net posts
      ctx.fillStyle = "#e5e7eb";
      ctx.strokeStyle = "#00e5ff";
      ctx.lineWidth = 1.5;
      for (const postX of [x0 - 6, x1 + 6]) {
        ctx.beginPath();
        ctx.arc(postX, netY, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }

      const farDoublesLongY = y0 + DOUBLES_LONG_FAR * courtH;
      const nearDoublesLongY = y0 + DOUBLES_LONG_NEAR * courtH;
      const p1ServiceY = y0 + SHORT_FAR * courtH;
      const p2ServiceY = y0 + SHORT_NEAR * courtH;

      // Doubles long service lines, 0.76m inside each baseline.
      ctx.strokeStyle = "#374151";
      ctx.lineWidth = 1;
      for (const serviceY of [farDoublesLongY, nearDoublesLongY]) {
        ctx.beginPath();
        ctx.moveTo(x0, serviceY);
        ctx.lineTo(x1, serviceY);
        ctx.stroke();
      }

      // Center Lines (baseline to short service line)
      const centerX = x0 + 0.5 * courtW;
      ctx.strokeStyle = "#374151";
      ctx.lineWidth = 1;

      // P1 center line
      ctx.beginPath();
      ctx.moveTo(centerX, y0);
      ctx.lineTo(centerX, p1ServiceY);
      ctx.stroke();

      // P2 center line
      ctx.beginPath();
      ctx.moveTo(centerX, p2ServiceY);
      ctx.lineTo(centerX, y1);
      ctx.stroke();

      // Short service lines sit 1.98m from the net.
      ctx.strokeStyle = "#4b5563";
      ctx.beginPath();
      ctx.moveTo(x0, p1ServiceY);
      ctx.lineTo(x1, p1ServiceY);
      ctx.moveTo(x0, p2ServiceY);
      ctx.lineTo(x1, p2ServiceY);
      ctx.stroke();

      // Labels for Court Halves
      ctx.fillStyle = "#6b7280";
      ctx.font = "bold 9px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("SÂN XA (VĐV 2)", centerX, y0 + 16);
      ctx.fillText("SÂN GẦN (VĐV 1)", centerX, y1 - 8);

      if (currentFrame) {
        // 1. Render Shuttlecock Trajectory Trail (Smooth EMA Filtered)
        if (
          currentFrame.shuttle &&
          currentFrame.shuttle.visible &&
          currentFrame.shuttle.projection_valid === true &&
          currentFrame.shuttle.x_norm !== undefined
        ) {
          const rawSx = x0 + Math.max(0.02, Math.min(0.98, currentFrame.shuttle.x_norm)) * courtW;
          const rawSy = y0 + Math.max(0.02, Math.min(0.98, currentFrame.shuttle.y_norm)) * courtH;

          const sx = rawSx;
          const sy = rawSy;
          if (lastShuttleFrameRef.current !== currentFrame.frame_idx) {
            if (
              lastShuttleFrameRef.current !== null &&
              currentFrame.frame_idx <= lastShuttleFrameRef.current
            ) {
              shuttleTrailRef.current = [];
            }
            shuttleTrailRef.current.push({ x: sx, y: sy });
            shuttleTrailRef.current = shuttleTrailRef.current.slice(-10);
            lastShuttleFrameRef.current = currentFrame.frame_idx;
          }

          // Draw trailing glowing line
          if (shuttleTrailRef.current.length > 1) {
            ctx.beginPath();
            for (let i = 0; i < shuttleTrailRef.current.length; i++) {
              const pt = shuttleTrailRef.current[i];
              if (i === 0) ctx.moveTo(pt.x, pt.y);
              else ctx.lineTo(pt.x, pt.y);
            }
            ctx.strokeStyle = "rgba(255, 255, 255, 0.55)";
            ctx.lineWidth = 2.2;
            ctx.stroke();
          }

          // Shuttle glowing white head
          ctx.shadowColor = "#ffffff";
          ctx.shadowBlur = 12;
          ctx.fillStyle = "#ffffff";
          ctx.beginPath();
          ctx.arc(sx, sy, 5.0, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = "#00e5ff";
          ctx.lineWidth = 1.5;
          ctx.stroke();
          ctx.shadowBlur = 0;
        } else {
          // Clear trail if shuttle is not visible
          shuttleTrailRef.current = [];
          lastShuttleFrameRef.current = currentFrame.frame_idx;
        }

        // 2. Render Players & Motion Trails (Supports 1v1 Singles & 2v2 Doubles)
        const playerColorMap: Record<number, { solid: string; glow: string; ring: string }> = {
          1: { solid: "#00e5ff", glow: "#00e5ff", ring: "rgba(0, 229, 255, 0.4)" },
          3: { solid: "#38bdf8", glow: "#38bdf8", ring: "rgba(56, 189, 248, 0.4)" },
          2: { solid: "#f59e0b", glow: "#f59e0b", ring: "rgba(245, 158, 11, 0.4)" },
          4: { solid: "#fb923c", glow: "#fb923c", ring: "rgba(251, 146, 60, 0.4)" },
        };

        currentFrame.players.forEach((p) => {
          const pId = p.player_id || 1;
          const colors = playerColorMap[pId] || playerColorMap[1];
          const px = x0 + Math.max(0.04, Math.min(0.96, p.x_norm)) * courtW;
          const py = y0 + Math.max(0.04, Math.min(0.96, p.y_norm)) * courtH;

          // Pulsing radar ripple ring
          const ringRadius = 13 + pulse * 2.5;
          ctx.strokeStyle = colors.ring;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.arc(px, py, ringRadius, 0, Math.PI * 2);
          ctx.stroke();

          // Athlete silhouette marker
          ctx.shadowColor = colors.glow;
          ctx.shadowBlur = 10;
          ctx.fillStyle = colors.solid;
          ctx.beginPath();
          ctx.arc(px, py - 5, 3.2, 0, Math.PI * 2);
          ctx.fill();
          ctx.beginPath();
          ctx.moveTo(px, py - 1.5);
          ctx.lineTo(px - 6, py + 7);
          ctx.lineTo(px + 6, py + 7);
          ctx.closePath();
          ctx.fill();
          ctx.shadowBlur = 0;
        });
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [currentFrame, width, height, showVoronoi]);

  return (
    <div className="flex flex-col items-center w-full">
      <div className="rounded-2xl overflow-hidden border border-gray-700/80 shadow-2xl bg-surface">
        <canvas ref={canvasRef} width={width} height={height} className="block" />
      </div>
    </div>
  );
};
