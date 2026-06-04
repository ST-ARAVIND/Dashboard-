import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import OptionChainPage from "./pages/OptionChain";
import Analytics from "./pages/Analytics";
import Scanners from "./pages/Scanners";
import SymbolDetail from "./pages/SymbolDetail";
import News from "./pages/News";
import Watchlist from "./pages/Watchlist";
import Alerts from "./pages/Alerts";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="/chain" element={<OptionChainPage />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/scanners" element={<Scanners />} />
        <Route path="/symbol/:token" element={<SymbolDetail />} />
        <Route path="/news" element={<News />} />
        <Route path="/watchlist" element={<Watchlist />} />
        <Route path="/alerts" element={<Alerts />} />
      </Route>
    </Routes>
  );
}
