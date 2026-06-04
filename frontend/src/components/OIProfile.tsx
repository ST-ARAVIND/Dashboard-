import type { ChainRow } from "../api/types";
import { compact } from "../lib/format";

// Horizontal OI distribution: call OI grows left, put OI grows right, per strike.
// Highlights ATM and marks the strikes with the largest call/put OI walls.
export function OIProfile({
  rows,
  atmStrike,
}: {
  rows: ChainRow[];
  atmStrike: number | null;
}) {
  const maxOI = Math.max(
    1,
    ...rows.flatMap((r) => [(r.ce?.oi ?? 0), (r.pe?.oi ?? 0)])
  );
  // Find the biggest CE and PE OI walls (resistance / support).
  let ceWall = { strike: 0, oi: 0 };
  let peWall = { strike: 0, oi: 0 };
  rows.forEach((r) => {
    if ((r.ce?.oi ?? 0) > ceWall.oi) ceWall = { strike: r.strike, oi: r.ce!.oi! };
    if ((r.pe?.oi ?? 0) > peWall.oi) peWall = { strike: r.strike, oi: r.pe!.oi! };
  });

  return (
    <div>
      <div className="flex items-center justify-between text-[10px] text-muted mb-2">
        <span className="text-bull/80 font-semibold">◄ CALL OI (resistance)</span>
        <span>Strike</span>
        <span className="text-bear/80 font-semibold">PUT OI (support) ►</span>
      </div>
      <div className="flex flex-col gap-[3px]">
        {rows.map((r) => {
          const ceW = ((r.ce?.oi ?? 0) / maxOI) * 100;
          const peW = ((r.pe?.oi ?? 0) / maxOI) * 100;
          const isATM = r.strike === atmStrike;
          return (
            <div key={r.strike} className="flex items-center gap-2 h-[18px]">
              {/* CE side — bar grows from the right edge leftward */}
              <div className="flex-1 flex justify-end">
                <div
                  className="h-full rounded-l flex items-center justify-end pr-1 text-[8px] text-ink"
                  style={{
                    width: `${ceW}%`,
                    background: `linear-gradient(90deg, transparent, ${
                      r.strike === ceWall.strike ? "rgba(21,128,61,0.55)" : "rgba(21,128,61,0.28)"
                    })`,
                  }}
                >
                  {(r.ce?.oi ?? 0) > maxOI * 0.25 ? compact(r.ce?.oi) : ""}
                </div>
              </div>
              {/* Strike */}
              <div
                className={`num text-[10px] font-semibold w-[58px] text-center rounded ${
                  isATM ? "bg-accent/20 text-accent" : "text-ink"
                }`}
              >
                {r.strike}
              </div>
              {/* PE side — grows rightward */}
              <div className="flex-1">
                <div
                  className="h-full rounded-r flex items-center pl-1 text-[8px] text-ink"
                  style={{
                    width: `${peW}%`,
                    background: `linear-gradient(270deg, transparent, ${
                      r.strike === peWall.strike ? "rgba(192,57,43,0.55)" : "rgba(192,57,43,0.28)"
                    })`,
                  }}
                >
                  {(r.pe?.oi ?? 0) > maxOI * 0.25 ? compact(r.pe?.oi) : ""}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex gap-4 text-[10px] text-muted mt-3 pt-2 border-t border-line">
        <span>
          Call wall (resistance): <b className="text-bull num">{ceWall.strike || "—"}</b>
        </span>
        <span>
          Put wall (support): <b className="text-bear num">{peWall.strike || "—"}</b>
        </span>
      </div>
    </div>
  );
}
