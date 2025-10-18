import { CheckCircle2 } from "lucide-react";
import type React from "react";
import type { TaskListItem } from "@/client/types.gen";
import { TaskPriority } from "@/client/types.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface TaskItemProps {
  task: TaskListItem;
  onToggle: (id: number, completed: boolean) => void;
  onDelete: (id: number) => void;
}

const TaskItem: React.FC<TaskItemProps> = ({ task, onToggle, onDelete }) => {
  const getPriorityColor = (priority: TaskPriority) => {
    switch (priority) {
      case TaskPriority.HIGH:
        return "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400";
      case TaskPriority.MEDIUM:
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400";
      case TaskPriority.LOW:
        return "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400";
    }
  };

  return (
    <Card className="group hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={() => onToggle(task.id, !task.completed)}
            className={`mt-1 h-5 w-5 rounded-full border-2 flex items-center justify-center transition-colors ${
              task.completed
                ? "bg-green-500 border-green-500 text-white"
                : "border-gray-300 hover:border-green-500"
            }`}
          >
            {task.completed && <CheckCircle2 className="h-3 w-3" />}
          </button>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3
                className={`font-medium ${
                  task.completed
                    ? "text-slate-500 line-through"
                    : "text-slate-900 dark:text-white"
                }`}
              >
                {task.title}
              </h3>
              <Badge className={getPriorityColor(task.priority)}>
                {task.priority}
              </Badge>
            </div>
            {task.description && (
              <p
                className={`text-sm ${
                  task.completed
                    ? "text-slate-400 line-through"
                    : "text-slate-600 dark:text-slate-300"
                }`}
              >
                {task.description}
              </p>
            )}
            <p className="text-xs text-slate-400 mt-1">
              Created {task.created_at.toLocaleString()}
            </p>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(task.id)}
            className="opacity-0 group-hover:opacity-100 transition-opacity text-red-500 hover:text-red-700 hover:bg-red-50"
          >
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default TaskItem;
