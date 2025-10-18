import { Link } from "@tanstack/react-router";
import { ArrowLeft, Shield, Target, Zap } from "lucide-react";
import type React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const AboutPage: React.FC = () => {
  return (
    <div className="py-20 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <Link to="/">
            <Button variant="outline" size="sm" className="mb-6">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Tasks
            </Button>
          </Link>
          <div className="mb-8">
            <Badge variant="secondary" className="mb-4">
              About Blank
            </Badge>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white mb-6">
            Simple Task Management
          </h1>
          <p className="text-xl text-slate-600 dark:text-slate-300 mb-8">
            A clean, modern task manager built with React, TypeScript, and
            shadcn/ui components.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-12">
          <Card>
            <CardHeader>
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/20 rounded-lg flex items-center justify-center text-blue-600 dark:text-blue-400 mb-4">
                <Target className="h-6 w-6" />
              </div>
              <CardTitle>Stay Organized</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-base">
                Keep track of all your tasks in one place. Create, organize, and
                prioritize your work to stay focused on what matters most.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="w-12 h-12 bg-green-100 dark:bg-green-900/20 rounded-lg flex items-center justify-center text-green-600 dark:text-green-400 mb-4">
                <Zap className="h-6 w-6" />
              </div>
              <CardTitle>Built for Speed</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-base">
                Fast, responsive interface built with modern web technologies.
                Your tasks are saved locally for instant access.
              </CardDescription>
            </CardContent>
          </Card>
        </div>

        <div className="text-center bg-slate-50 dark:bg-slate-800 rounded-lg p-8">
          <Shield className="h-12 w-12 text-purple-600 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
            Privacy First
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-300 mb-6">
            Your tasks are stored locally in your browser. No accounts, no cloud
            sync, no tracking - just your tasks, your way.
          </p>
          <Link to="/">
            <Button size="lg">Start Managing Tasks</Button>
          </Link>
        </div>

        <div className="mt-12">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
            Features
          </h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="text-sm">
              <div className="font-medium text-slate-900 dark:text-white">
                ✓ Create & Edit Tasks
              </div>
              <div className="text-slate-600 dark:text-slate-300">
                Add tasks with descriptions and priorities
              </div>
            </div>
            <div className="text-sm">
              <div className="font-medium text-slate-900 dark:text-white">
                ✓ Priority Levels
              </div>
              <div className="text-slate-600 dark:text-slate-300">
                Organize by High, Medium, and Low priority
              </div>
            </div>
            <div className="text-sm">
              <div className="font-medium text-slate-900 dark:text-white">
                ✓ Search & Filter
              </div>
              <div className="text-slate-600 dark:text-slate-300">
                Find tasks quickly with search and filters
              </div>
            </div>
            <div className="text-sm">
              <div className="font-medium text-slate-900 dark:text-white">
                ✓ Mark Complete
              </div>
              <div className="text-slate-600 dark:text-slate-300">
                Check off completed tasks
              </div>
            </div>
            <div className="text-sm">
              <div className="font-medium text-slate-900 dark:text-white">
                ✓ Local Storage
              </div>
              <div className="text-slate-600 dark:text-slate-300">
                Tasks persist between browser sessions
              </div>
            </div>
            <div className="text-sm">
              <div className="font-medium text-slate-900 dark:text-white">
                ✓ Dark Mode
              </div>
              <div className="text-slate-600 dark:text-slate-300">
                Comfortable viewing in any lighting
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AboutPage;
