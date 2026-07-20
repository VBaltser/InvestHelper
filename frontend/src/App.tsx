import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { BondScreenerPage } from "./pages/BondScreenerPage";
import { DfaScreenerPage } from "./pages/DfaScreenerPage";
import { OperationsPage } from "./pages/OperationsPage";
import { PortfolioPage } from "./pages/PortfolioPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<PortfolioPage />} />
          <Route path="/operations" element={<OperationsPage />} />
          <Route path="/bonds" element={<BondScreenerPage />} />
          <Route path="/dfa" element={<DfaScreenerPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
