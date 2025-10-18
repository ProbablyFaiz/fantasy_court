import { CheckSquare, Github } from "lucide-react";
import type React from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export const Footer: React.FC = () => {
  return (
    <>
      <Separator className="max-w-7xl mx-auto" />
      <footer className="py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="flex items-center mb-4 md:mb-0">
              <CheckSquare className="h-6 w-6 text-blue-600" />
              <span className="ml-2 text-lg font-semibold text-slate-900 dark:text-white">
                Blank
              </span>
            </div>
            <div className="flex space-x-6">
              <Button variant="ghost" size="sm">
                <Github className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <Separator className="my-6" />
          <div className="text-center text-slate-500 dark:text-slate-400">
            <p>&copy; 2024 Blank - Simple Task Management</p>
          </div>
        </div>
      </footer>
    </>
  );
};
