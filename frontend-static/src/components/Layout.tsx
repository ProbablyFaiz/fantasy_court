import type { ReactNode } from "react";

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <main className="flex-grow">{children}</main>

      <footer
        id="about"
        className="mt-2 pt-8 border-t border-border text-center text-sm text-foreground/60"
      >
        <div className="max-w-4xl mx-auto px-6 pb-8">
          <p>
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
        </div>
      </footer>
    </div>
  );
}
