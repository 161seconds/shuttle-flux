import React, { useRef, useEffect } from "react";
import { FrameRecord } from "../lib/api";

interface RadarCanvasProps {
  currentFrame?: FrameRecord;
  width?: number;
  height?: number;
}

export const RadarCanvas: React.FC<RadarCanvasProps> = ({
  currentFrame,
  width = 280,
  height = 540,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const trailingRef = useRef<Array<{ x: number; y: number }>>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Clear background
    ctx.fillStyle = "#12171f";
    ctx.fillRect(0, 0, width, height);

    const pad = 24;
    const courtW = width - 2 * pad;
    const courtH = height - 2 * pad;
    const x0 = pad;
    const y0 = pad;
    const x1 = pad + courtW;
    const y1 = pad + courtH;

    // Court Floor
    ctx.fillStyle = "#1a2230";
    ctx.fillRect(x0, y0, courtW, courtH);

    // Court Outer Boundary
    ctx.strokeStyle = "#4b5563";
    ctx.lineWidth = 2;
    ctx.strokeRect(x0, y0, courtW, courtH);

    // Net Line (y = 0.5)
    const netY = y0 + 0.5 * courtH;
    ctx.strokeStyle = "#00e5ff";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(x0 - 4, netY);
    ctx.lineTo(x1 + 4, netY);
    ctx.stroke();

    // Center Lines
    const centerX = x0 + 0.5 * courtW;
    ctx.strokeStyle = "#374151";
    ctx.lineWidth = 1;

    // P1 Center line (Baseline to service line)
    ctx.beginPath();
    ctx.moveTo(centerX, y0);
    ctx.lineTo(centerX, y0 + 0.35 * courtH);
    ctx.stroke();

    // P2 Center line (Service line to baseline)
    ctx.beginPath();
    ctx.moveTo(centerX, y0 + 0.65 * courtH);
    ctx.lineTo(centerX, y1);
    ctx.stroke();

    // Short Service Lines (~35% and ~65%)
    const p1ServiceY = y0 + 0.35 * courtH;
    const p2ServiceY = y0 + 0.65 * courtH;
    ctx.beginPath();
    ctx.moveTo(x0, p1ServiceY);
    ctx.lineTo(x1, p1ServiceY);
    ctx.moveTo(x0, p2ServiceY);
    ctx.lineTo(x1, p2ServiceY);
    ctx.stroke();

    // Labels for players side
    ctx.fillStyle = "#6b7280";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("NEAR COURT (P1)", centerX, y0 + 16);
    ctx.fillText("FAR COURT (P2)", centerX, y1 - 8);

    if (!currentFrame) return;

    // Draw Trailing Shuttle Trail
    if (currentFrame.shuttle && currentFrame.shuttle.visible) {
      const sx = x0 + currentFrame.shuttle.x_norm * courtW;
      const sy = y0 + currentFrame.shuttle.y_norm * courtH;
      trailingRef.current.push({ x: sx, y: sy });
      if (trailingRef.current.length > 12) {
        trailingRef.current.shift();
      }

      ctx.beginPath();
      for (let i = 0; i < trailingRef.current.length; i++) {
        const pt = trailingRef.current[i];
        if (i === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      }
      ctx.strokeStyle = "rgba(255, 234, 0, 0.4)";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Draw Shuttle
      ctx.fillStyle = "#ffea00";
      ctx.beginPath();
      ctx.arc(sx, sy, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Draw Players
    currentFrame.players.forEach((p) => {
      const px = x0 + p.x_norm * courtW;
      const py = y0 + p.y_norm * courtH;
      const isP1 = p.player_id === 1;

      // Glow effect
      ctx.fillStyle = isP1 ? "rgba(0, 229, 255, 0.25)" : "rgba(255, 145, 0, 0.25)";
      ctx.beginPath();
      ctx.arc(px, py, 14, 0, Math.PI * 2);
      ctx.fill();

      // Solid player dot
      ctx.fillStyle = isP1 ? "#00e5ff" : "#ff9100";
      ctx.beginPath();
      ctx.arc(px, py, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label text
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 9px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`P${p.player_id}`, px, py);
    });
  }, [currentFrame, width, height]);

  return (
    <div className="flex flex-col items-center">
      <div className="rounded-xl overflow-hidden border border-gray-700 shadow-2xl bg-surface">
        <canvas ref={canvasRef} width={width} height={height} className="block" />
      </div>
      <div className="flex items-center space-x-6 mt-3 text-xs font-semibold">
        <div className="flex items-center space-x-2">
          <span className="w-3 h-3 rounded-full bg-brand-cyan"></span>
          <span className="text-gray-300">Player 1</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-3 h-3 rounded-full bg-brand-amber"></span>
          <span className="text-gray-300">Player 2</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-3 h-3 rounded-full bg-brand-yellow"></span>
          <span className="text-gray-300">Shuttlecock</span>
        </div>
      </div>
    </div>
  );
};
