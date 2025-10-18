import { CheckCircle2 } from "lucide-react";
import type React from "react";
import type { TaskListItem } from "@/client/types.gen";
import { Card } from "@/components/ui/card";
import TaskItem from "@/features/home/TaskItem";

interface TaskListProps {
  tasks: TaskListItem[];
  hasAnyTasks: boolean;
  onToggleTask: (id: number, completed: boolean) => void;
  onDeleteTask: (id: number) => void;
}

const TaskList: React.FC<TaskListProps> = ({
  tasks,
  hasAnyTasks,
  onToggleTask,
  onDeleteTask,
}) => {
  if (tasks.length === 0) {
    return (
      <Card className="p-8 text-center">
        <div className="text-slate-400 dark:text-slate-500">
          <CheckCircle2 className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium mb-2">
            {!hasAnyTasks ? "No tasks yet" : "No tasks match your filter"}
          </p>
          <p className="text-sm">
            {!hasAnyTasks
              ? "Add your first task to get started!"
              : "Try adjusting your search or filter"}
          </p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {tasks.map((task) => (
        <TaskItem
          key={task.id}
          task={task}
          onToggle={onToggleTask}
          onDelete={onDeleteTask}
        />
      ))}
    </div>
  );
};

export default TaskList;
