import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { EpisodeEditPage } from "./pages/EpisodeEditPage";
import { LoginPage } from "./pages/LoginPage";
import { PublishPage } from "./pages/PublishPage";
import { ShowEditPage } from "./pages/ShowEditPage";
import { ShowsPage } from "./pages/ShowsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A 401 or 403 will not fix itself on retry, so do not hammer the API.
      retry: (failureCount, error) => {
        const status = (error as { status?: number }).status;
        if (status === 401 || status === 403) return false;
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
      staleTime: 10_000,
    },
  },
});

function Shell() {
  const { token } = useAuth();
  if (!token) return <LoginPage />;

  return (
    <Router>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/shows" element={<ShowsPage />} />
          <Route path="/shows/:id" element={<ShowEditPage />} />
          <Route path="/episodes/:id" element={<EpisodeEditPage />} />
          <Route path="/publish" element={<PublishPage />} />
          <Route path="*" element={<Navigate to="/shows" replace />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </QueryClientProvider>
  );
}
