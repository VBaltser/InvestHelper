import { useEffect, useState } from "react";
import { getDiagnostics, type DiagnosticsResult } from "../api";

interface Props {
  error: string;
  hint?: string;
}

export function ErrorState({ error, hint }: Props) {
  const [diagnostics, setDiagnostics] = useState<DiagnosticsResult | null>(null);

  useEffect(() => {
    getDiagnostics()
      .then(setDiagnostics)
      .catch(() => setDiagnostics(null));
  }, []);

  return (
    <div className="state-box error">
      <strong>Ошибка</strong>
      <p>{error}</p>
      {hint && <p className="state-hint">{hint}</p>}
      {diagnostics && !diagnostics.healthy && (
        <div className="diagnostics">
          <p className="diagnostics-title">Диагностика сети</p>
          <ul>
            <li>{diagnostics.tcp.message}</li>
            <li>{diagnostics.api.message}</li>
          </ul>
          <ul>
            {diagnostics.suggestions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
