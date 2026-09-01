import React, { useRef, useEffect } from "react";
import { FrameRecord } from "../lib/api";

interface RadarCanvasProps {
  currentFrame?: FrameRecord;
  width?: number;
  height?: number;
  showVoronoi?: boolean;
}

export const RadarCanvas: React.FC<RadarCanvasProps> = ({
  currentFrame,
  width = 280,
  height = 500,
  showVoronoi = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const shuttleTrailRef = useRef<Array<{ x: number; y: number; time: number }>>([]);
  const p1TrailRef = useRef<Array<{ x: number; y: number }>>([]);
  const p2TrailRef = useRef<Array<{ x: number; y: number }>>([]);
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

      // Doubles sidelines (outer) & Singles sidelines (inner - 6% padding)
      const singlesPad = courtW * 0.07;
      ctx.strokeStyle = "#1f2937";
      ctx.lineWidth = 1;
      ctx.strokeRect(x0 + singlesPad, y0, courtW - 2 * singlesPad, courtH);

      // Net Line (y = 0.5) with cyan neon glow
      const netY = y0 + 0.5 * courtH;
      ctx.shadowColor = "#00e5ff";
      ctx.shadowBlur = 8;
      ctx.strokeStyle = "#00e5ff";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(x0 - 6, netY);
      ctx.lineTo(x1 + 6, netY);
      ctx.stroke();
      ctx.shadowBlur = 0; // Reset shadow

      // Center Lines (P1 baseline to short service, P2 short service to baseline)
      const centerX = x0 + 0.5 * courtW;
      ctx.strokeStyle = "#374151";
      ctx.lineWidth = 1;

      // P1 center line
      ctx.beginPath();
      ctx.moveTo(centerX, y0);
      ctx.lineTo(centerX, y0 + 0.35 * courtH);
      ctx.stroke();

      // P2 center line
      ctx.beginPath();
      ctx.moveTo(centerX, y0 + 0.65 * courtH);
      ctx.lineTo(centerX, y1);
      ctx.stroke();

      // Short Service Lines (at ~35% and ~65%)
      const p1ServiceY = y0 + 0.35 * courtH;
      const p2ServiceY = y0 + 0.65 * courtH;
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
        if (currentFrame.shuttle && currentFrame.shuttle.visible && currentFrame.shuttle.x_norm !== undefined) {
          const rawSx = x0 + Math.max(0.02, Math.min(0.98, currentFrame.shuttle.x_norm)) * courtW;
          const rawSy = y0 + Math.max(0.02, Math.min(0.98, currentFrame.shuttle.y_norm)) * courtH;

          // Smooth coordinate filtering across frame ticks
          const lastPt = shuttleTrailRef.current[shuttleTrailRef.current.length - 1];
          let sx = rawSx;
          let sy = rawSy;

          if (lastPt) {
            // If distance is reasonable, apply gentle smoothing
            const dist = Math.hypot(rawSx - lastPt.x, rawSy - lastPt.y);
            if (dist < courtW * 0.4) {
              sx = 0.45 * lastPt.x + 0.55 * rawSx;
              sy = 0.45 * lastPt.y + 0.55 * rawSy;
            }
          }

          shuttleTrailRef.current.push({ x: sx, y: sy, time: Date.now() });
          if (shuttleTrailRef.current.length > 10) {
            shuttleTrailRef.current.shift();
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
        }

        // 2. Render Players & Motion Trails
        currentFrame.players.forEach((p) => {
          const isP1 = p.player_id === 1;
          const px = x0 + Math.max(0.05, Math.min(0.95, p.x_norm)) * courtW;
          const py = y0 + Math.max(0.05, Math.min(0.95, p.y_norm)) * courtH;

          // Track trails
          const trailList = isP1 ? p1TrailRef.current : p2TrailRef.current;
          trailList.push({ x: px, y: py });
          if (trailList.length > 10) trailList.shift();

          // Draw subtle motion line
          if (trailList.length > 1) {
            ctx.beginPath();
            for (let i = 0; i < trailList.length; i++) {
              const t = trailList[i];
              if (i === 0) ctx.moveTo(t.x, t.y);
              else ctx.lineTo(t.x, t.y);
            }
            ctx.strokeStyle = isP1 ? "rgba(0, 229, 255, 0.25)" : "rgba(255, 145, 0, 0.25)";
            ctx.lineWidth = 2;
            ctx.stroke();
          }

          // Pulsing radar ripple ring
          const ringRadius = 14 + pulse * 3;
          ctx.strokeStyle = isP1 ? "rgba(0, 229, 255, 0.4)" : "rgba(255, 145, 0, 0.4)";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(px, py, ringRadius, 0, Math.PI * 2);
          ctx.stroke();

          // Solid Player Dot
          ctx.shadowColor = isP1 ? "#00e5ff" : "#ff9100";
          ctx.shadowBlur = 10;
          ctx.fillStyle = isP1 ? "#00e5ff" : "#ff9100";
          ctx.beginPath();
          ctx.arc(px, py, 8, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;

          // Player number label
          ctx.fillStyle = "#000000";
          ctx.font = "bold 9px sans-serif";
          ctx.textAlign = "center";
          ctx.fillText(isP1 ? "1" : "2", px, py + 3);
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
