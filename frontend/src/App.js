import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ThemeProvider, useTheme } from "next-themes";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Shell } from "@/components/Shell";
import Landing from "@/pages/Landing";
import Auth from "@/pages/Auth";
import Onboarding from "@/pages/Onboarding";
import Home from "@/pages/Home";
import Generating from "@/pages/Generating";
import Report from "@/pages/Report";
import Compare from "@/pages/Compare";
import Recommend from "@/pages/Recommend";
import Community from "@/pages/Community";
import Account from "@/pages/Account";
import Trust from "@/pages/Trust";
import PublicReport from "@/pages/PublicReport";
import Contribute from "@/pages/Contribute";

const Loading = () => (
  <div className="grid min-h-screen place-items-center">
    <p className="mono text-xs uppercase tracking-[0.3em] text-zinc-600 caret">booting localiq</p>
  </div>
);

const Protected = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/auth" replace />;
  return <Shell>{children}</Shell>;
};

const Routing = () => (
  <Routes>
    <Route path="/" element={<Landing />} />
    <Route path="/auth" element={<Auth />} />
    <Route path="/r/:token" element={<PublicReport />} />
    <Route path="/c/:token" element={<Contribute />} />
    <Route path="/onboarding" element={<Onboarding />} />
    <Route path="/app" element={<Protected><Home /></Protected>} />
    <Route path="/app/generating/:jobId" element={<Protected><Generating /></Protected>} />
    <Route path="/app/report/:reportId" element={<Protected><Report /></Protected>} />
    <Route path="/app/compare" element={<Protected><Compare /></Protected>} />
    <Route path="/app/recommend" element={<Protected><Recommend /></Protected>} />
    <Route path="/app/community" element={<Protected><Community /></Protected>} />
    <Route path="/app/account" element={<Protected><Account /></Protected>} />
    <Route path="/app/trust" element={<Protected><Trust /></Protected>} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
);

const Notifications = () => {
  const { resolvedTheme } = useTheme();
  return (
    <Toaster
      theme={resolvedTheme === "dark" ? "dark" : "light"}
      position="bottom-right"
      toastOptions={{
        style: {
          borderRadius: 8,
          fontFamily: "IBM Plex Mono, monospace",
          fontSize: 12,
        },
      }}
    />
  );
};

export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false} storageKey="lq-theme" disableTransitionOnChange>
      <AuthProvider>
        <BrowserRouter>
          <Routing />
          <Notifications />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
