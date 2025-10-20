import type { ReactNode } from "react";

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <main className="flex-grow">{children}</main>

      <footer className="mt-2 pt-8 border-t border-border text-center text-sm text-foreground/60">
        <div className="max-w-4xl mx-auto px-6 pb-8">
          <p>
            This project is inspired by the Fantasy Court segment from{" "}
            <span className="font-equity italic">
              The Ringer Fantasy Football Show
            </span>
            . Not affiliated with The Ringer.
          </p>
        </div>
      </footer>
    </div>
  );
}
