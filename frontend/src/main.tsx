import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import * as Sentry from "@sentry/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { client } from "@/client/client.gen";

const API_BASE_URL = import.meta.env.VITE_BLANK_API_URL;
const SENTRY_DSN = import.meta.env.VITE_BLANK_SENTRY_DSN;

if (!API_BASE_URL) {
  throw new Error("VITE_BLANK_API_URL is not set");
}

if (!SENTRY_DSN) {
  console.warn(
    "VITE_BLANK_SENTRY_DSN is not set, Sentry will not be initialized",
  );
}

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.VITE_BLANK_ENV || "dev",
  });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10000,
    },
  },
});
client.setConfig({
  baseURL: API_BASE_URL,
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
