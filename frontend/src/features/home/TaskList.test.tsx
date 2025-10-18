import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { type TaskListItem, TaskPriority } from "@/client/types.gen";
import TaskList from "./TaskList";

const mockTasks: TaskListItem[] = [
  {
    id: 1,
    title: "Buy groceries",
    description: "Milk, eggs, bread",
    completed: false,
    priority: TaskPriority.HIGH,
    created_at: new Date("2024-01-01T10:00:00Z"),
    updated_at: new Date("2024-01-01T10:00:00Z"),
  },
  {
    id: 2,
    title: "Review pull request",
    description: null,
    completed: true,
    priority: TaskPriority.MEDIUM,
    created_at: new Date("2024-01-02T10:00:00Z"),
    updated_at: new Date("2024-01-02T10:00:00Z"),
  },
];

describe("TaskList Integration", () => {
  const mockOnToggleTask = vi.fn();
  const mockOnDeleteTask = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("displays empty state when no tasks exist", () => {
    render(
      <TaskList
        tasks={[]}
        hasAnyTasks={false}
        onToggleTask={mockOnToggleTask}
        onDeleteTask={mockOnDeleteTask}
      />,
    );

    expect(screen.getByText("No tasks yet")).toBeInTheDocument();
  });

  it("displays filtered empty state when tasks exist elsewhere", () => {
    render(
      <TaskList
        tasks={[]}
        hasAnyTasks={true}
        onToggleTask={mockOnToggleTask}
        onDeleteTask={mockOnDeleteTask}
      />,
    );

    expect(screen.getByText("No tasks match your filter")).toBeInTheDocument();
  });

  it("renders tasks with their core information", () => {
    render(
      <TaskList
        tasks={mockTasks}
        hasAnyTasks={true}
        onToggleTask={mockOnToggleTask}
        onDeleteTask={mockOnDeleteTask}
      />,
    );

    // Verify tasks are displayed
    expect(screen.getByText("Buy groceries")).toBeInTheDocument();
    expect(screen.getByText("Milk, eggs, bread")).toBeInTheDocument();
    expect(screen.getByText("Review pull request")).toBeInTheDocument();

    // Verify priority badges work
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    expect(screen.getByText("MEDIUM")).toBeInTheDocument();
  });

  it("handles task completion toggling", async () => {
    const user = userEvent.setup();

    render(
      <TaskList
        tasks={mockTasks}
        hasAnyTasks={true}
        onToggleTask={mockOnToggleTask}
        onDeleteTask={mockOnDeleteTask}
      />,
    );

    // Find and click the toggle button for the incomplete task
    const toggleButtons = screen.getAllByRole("button");
    const incompleteTaskToggle = toggleButtons.find((button) =>
      button
        .closest('[class*="group"]')
        ?.textContent?.includes("Buy groceries"),
    );

    await user.click(incompleteTaskToggle!);

    expect(mockOnToggleTask).toHaveBeenCalledWith(1, true);
  });

  it("handles task deletion", async () => {
    const user = userEvent.setup();

    render(
      <TaskList
        tasks={mockTasks.slice(0, 1)}
        hasAnyTasks={true}
        onToggleTask={mockOnToggleTask}
        onDeleteTask={mockOnDeleteTask}
      />,
    );

    // Find delete button - it's a ghost button with "Delete" text
    const deleteButton = screen.getByRole("button", { name: /delete/i });

    await user.click(deleteButton);

    expect(mockOnDeleteTask).toHaveBeenCalledWith(expect.any(Number));
  });

  it("shows visual distinction between completed and incomplete tasks", () => {
    render(
      <TaskList
        tasks={mockTasks}
        hasAnyTasks={true}
        onToggleTask={mockOnToggleTask}
        onDeleteTask={mockOnDeleteTask}
      />,
    );

    // Completed task should have line-through styling
    const completedTaskTitle = screen.getByText("Review pull request");
    expect(completedTaskTitle).toHaveClass("line-through");

    // Incomplete task should not have line-through
    const incompleteTaskTitle = screen.getByText("Buy groceries");
    expect(incompleteTaskTitle).not.toHaveClass("line-through");
  });
});
