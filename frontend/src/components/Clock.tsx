import { useEffect, useState } from "react";

// Live IST clock for the header.
export function Clock() {
  const [now, setNow] = useState("");
  useEffect(() => {
    const tick = () =>
      setNow(
        new Intl.DateTimeFormat("en-IN", {
          timeZone: "Asia/Kolkata",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }).format(new Date())
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <span className="num text-[12px] text-slate-400" title="Indian Standard Time">
      {now} <span className="text-muted">IST</span>
    </span>
  );
}
