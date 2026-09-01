import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { type Catalog, fetchCatalog } from "../api/catalog";

/**
 * One immutable document per session, so a fetch plus context is the whole of
 * the state management. A caching layer over a value that never invalidates
 * would be complexity with no counterpart benefit.
 */

type State =
  | { status: "loading"; catalog: null; error: null }
  | { status: "ready"; catalog: Catalog; error: null }
  | { status: "error"; catalog: null; error: string };

type ContextValue = State & { retry: () => void };

const CatalogContext = createContext<ContextValue | null>(null);

export function CatalogProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<State>({ status: "loading", catalog: null, error: null });
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    fetchCatalog()
      .then((catalog) => {
        if (!cancelled) setState({ status: "ready", catalog, error: null });
      })
      .catch((error: Error) => {
        if (!cancelled) setState({ status: "error", catalog: null, error: error.message });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  return <CatalogContext.Provider value={{ ...state, retry }}>{children}</CatalogContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCatalog(): ContextValue {
  const value = useContext(CatalogContext);
  if (!value) throw new Error("useCatalog must be used inside CatalogProvider");
  return value;
}
