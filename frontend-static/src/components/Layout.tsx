import { Moon, Sun } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

interface LayoutProps {
  children: ReactNode;
}

const THEME_STORAGE_KEY = "fantasy-court-theme";

type Theme = "light" | "dark";

export default function Layout({ children }: LayoutProps) {
  const [theme, setTheme] = useState<Theme | null>(null);
  const [mounted, setMounted] = useState(false);

  // Load theme from localStorage and apply it before mount to prevent flash
  useEffect(() => {
    setMounted(true);
    try {
      const savedTheme = localStorage.getItem(
        THEME_STORAGE_KEY,
      ) as Theme | null;
      if (savedTheme && ["light", "dark"].includes(savedTheme)) {
        setTheme(savedTheme);
        applyTheme(savedTheme);
      } else {
        // Detect system preference if no saved theme
        const prefersDark = window.matchMedia(
          "(prefers-color-scheme: dark)",
        ).matches;
        setTheme(prefersDark ? "dark" : "light");
      }
    } catch (error) {
      console.error("Failed to load theme:", error);
    }
  }, []);

  // Apply theme to document root
  const applyTheme = (newTheme: Theme | null) => {
    const root = document.documentElement;
    if (newTheme) {
      root.setAttribute("data-theme", newTheme);
    } else {
      root.removeAttribute("data-theme");
    }
  };

  // Toggle theme
  const toggleTheme = () => {
    const newTheme: Theme = theme === "light" ? "dark" : "light";
    setTheme(newTheme);
    applyTheme(newTheme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, newTheme);
    } catch (error) {
      console.error("Failed to save theme:", error);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <main className="flex-grow">{children}</main>

      <footer
        id="about"
        className="mt-2 pt-8 border-t border-border text-center text-sm text-foreground/60"
      >
        <div className="max-w-4xl mx-auto px-6 pb-8">
          <p className="mb-4">
            This project is inspired by the Fantasy Court segment from{" "}
            <a
              href="https://www.theringer.com/podcasts/the-ringer-fantasy-football-show"
              className="font-equity italic text-accent hover:underline transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              The Ringer Fantasy Football Show
            </a>
            . Not affiliated with The Ringer.
          </p>

          {mounted && theme && (
            <button
              onClick={toggleTheme}
              className="inline-flex items-center gap-2 p-2 text-foreground/60 hover:text-foreground/90 transition-colors"
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
              title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            >
              {theme === "light" ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )}
              <span className="text-xs">
                {theme === "light" ? "Light" : "Dark"} mode
              </span>
            </button>
          )}
        </div>
      </footer>
    </div>
  );
}
