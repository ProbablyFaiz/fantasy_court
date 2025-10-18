import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import type React from "react";
import { useState } from "react";
import {
  listTasksOptions,
  listTasksQueryKey,
} from "@/client/@tanstack/react-query.gen";
import { Default } from "@/client/sdk.gen";
import {
  type TaskCreate,
  TaskPriority,
  type TaskUpdate,
} from "@/client/types.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import TaskList from "@/features/home/TaskList";

type FilterType = "all" | "active" | "completed";

const HomePage: React.FC = () => {
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDescription, setNewTaskDescription] = useState("");
  const [newTaskPriority, setNewTaskPriority] = useState<TaskPriority>(
    TaskPriority.MEDIUM,
  );
  const [filter, setFilter] = useState<FilterType>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const queryClient = useQueryClient();

  const {
    data: tasks,
    isLoading,
    isError,
  } = useQuery({
    ...listTasksOptions({
      query: {
        page: 1,
        limit: 10,
      },
    }),
  });

  const { mutate: createTask } = useMutation({
    mutationFn: (task: TaskCreate) => {
      return Default.createTask({
        body: task,
      });
    },
  });

  const { mutate: updateTask } = useMutation({
    mutationFn: ({
      id,
      taskUpdate,
    }: {
      id: number;
      taskUpdate: TaskUpdate;
    }) => {
      return Default.updateTask({
        body: {
          ...taskUpdate,
        },
        path: {
          task_id: id,
        },
      });
    },
  });

  const { mutate: deleteTaskMutation } = useMutation({
    mutationFn: (id: number) => {
      return Default.deleteTask({
        path: {
          task_id: id,
        },
      });
    },
  });

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (isError) {
    return <div>Error loading tasks</div>;
  }

  const addTask = () => {
    if (!newTaskTitle.trim()) return;

    const newTask: TaskCreate = {
      title: newTaskTitle.trim(),
      description: newTaskDescription.trim() || null,
      priority: newTaskPriority,
    };
    createTask(newTask, {
      onSuccess: () => {
        setNewTaskTitle("");
        setNewTaskDescription("");
        setNewTaskPriority(TaskPriority.MEDIUM);
        setIsAddDialogOpen(false);
        queryClient.invalidateQueries({ queryKey: listTasksQueryKey() });
      },
    });
  };

  const toggleTask = (id: number, completed: boolean) => {
    updateTask(
      {
        id,
        taskUpdate: {
          completed,
        },
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: listTasksQueryKey() });
        },
      },
    );
  };

  const deleteTask = (id: number) => {
    deleteTaskMutation(id, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: listTasksQueryKey() });
      },
    });
  };

  const filteredTasks = tasks?.items.filter((task) => {
    const matchesFilter =
      filter === "all" ||
      (filter === "active" && !task.completed) ||
      (filter === "completed" && task.completed);

    const matchesSearch =
      task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.description?.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  const completedCount = tasks?.items.filter((task) => task.completed).length;
  const totalCount = tasks?.items.length;

  return (
    <div className="py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-2">
            Task Manager
          </h1>
          <p className="text-lg text-slate-600 dark:text-slate-300">
            Stay organized and get things done
          </p>
          {totalCount && totalCount > 0 && (
            <div className="flex justify-center gap-2 mt-4">
              <Badge variant="outline">{totalCount} total</Badge>
              <Badge variant="outline">{completedCount} completed</Badge>
              <Badge variant="outline">
                {totalCount - (completedCount ?? 0)} remaining
              </Badge>
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
            <Input
              placeholder="Search tasks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>

          <div className="flex gap-2">
            <Button
              variant={filter === "all" ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter("all")}
            >
              All
            </Button>
            <Button
              variant={filter === "active" ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter("active")}
            >
              Active
            </Button>
            <Button
              variant={filter === "completed" ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter("completed")}
            >
              Completed
            </Button>
          </div>

          <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
            <DialogTrigger asChild>
              <Button className="group">
                <Plus className="mr-2 h-4 w-4 group-hover:rotate-90 transition-transform" />
                Add Task
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add New Task</DialogTitle>
                <DialogDescription>
                  Create a new task to stay organized.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <div>
                  <Input
                    placeholder="Task title"
                    value={newTaskTitle}
                    onChange={(e) => setNewTaskTitle(e.target.value)}
                  />
                </div>
                <div>
                  <Input
                    placeholder="Description (optional)"
                    value={newTaskDescription}
                    onChange={(e) => setNewTaskDescription(e.target.value)}
                  />
                </div>
                <div>
                  <select
                    value={newTaskPriority}
                    onChange={(e) =>
                      setNewTaskPriority(e.target.value as TaskPriority)
                    }
                    className="w-full p-2 border rounded-md dark:bg-slate-800 dark:border-slate-600"
                  >
                    <option value="low">Low Priority</option>
                    <option value="medium">Medium Priority</option>
                    <option value="high">High Priority</option>
                  </select>
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={addTask}
                    disabled={!newTaskTitle.trim()}
                    className="flex-1"
                  >
                    Add Task
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setIsAddDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Tasks List */}
        <TaskList
          tasks={filteredTasks || []}
          hasAnyTasks={(tasks?.items.length ?? 0) > 0}
          onToggleTask={toggleTask}
          onDeleteTask={deleteTask}
        />
      </div>
    </div>
  );
};

export default HomePage;
