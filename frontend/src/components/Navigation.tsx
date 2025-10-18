import { Link } from "@tanstack/react-router";
import { CheckSquare } from "lucide-react";
import type React from "react";
import { Button } from "@/components/ui/button";

export const Navigation: React.FC = () => {
  return (
    <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-lg border-b border-slate-200 dark:bg-slate-900/80 dark:border-slate-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="flex items-center">
            <CheckSquare className="h-8 w-8 text-blue-600" />
            <span className="ml-2 text-xl font-bold text-slate-900 dark:text-white">
              Blank
            </span>
          </Link>
          <div className="flex items-center space-x-4">
            <Link
              to="/"
              activeProps={{
                className: "text-blue-600 dark:text-blue-400",
              }}
            >
              {({ isActive }) => (
                <Button variant={isActive ? "default" : "ghost"} size="sm">
                  Tasks
                </Button>
              )}
            </Link>
            <Link
              to="/about"
              activeProps={{
                className: "text-blue-600 dark:text-blue-400",
              }}
            >
              {({ isActive }) => (
                <Button variant={isActive ? "default" : "ghost"} size="sm">
                  About
                </Button>
              )}
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};
