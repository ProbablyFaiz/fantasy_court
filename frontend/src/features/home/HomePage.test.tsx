import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import HomePage from "./HomePage";

// Test wrapper component that provides React Query context
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const renderWithQueryClient = (ui: React.ReactElement) => {
  return render(ui, { wrapper: TestWrapper });
};

describe("HomePage Integration", () => {
  beforeEach(() => {
    // Reset any test state if needed
  });

  it("loads and displays tasks from API", async () => {
    renderWithQueryClient(<HomePage />);

    // Initially shows loading
    expect(screen.getByText("Loading...")).toBeInTheDocument();

    // After loading, shows tasks
    expect(await screen.findByText("Test Task 1")).toBeInTheDocument();
    expect(screen.getByText("Test Task 2")).toBeInTheDocument();
    expect(screen.getByText("Test description")).toBeInTheDocument();

    // Shows task counts in header
    expect(screen.getByText("2 total")).toBeInTheDocument();
    expect(screen.getByText("1 completed")).toBeInTheDocument();
    expect(screen.getByText("1 remaining")).toBeInTheDocument();
  });

  it("creates a new task through the dialog", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<HomePage />);

    // Wait for initial load
    await screen.findByText("Test Task 1");

    // Open add task dialog
    await user.click(screen.getByRole("button", { name: /add task/i }));

    // Fill out form
    await user.type(screen.getByPlaceholderText("Task title"), "New Task");
    await user.type(
      screen.getByPlaceholderText("Description (optional)"),
      "New description",
    );

    // Submit form
    await user.click(screen.getByRole("button", { name: "Add Task" }));

    // Verify task was added (dialog should close and task should appear)
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("filters tasks correctly", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<HomePage />);

    // Wait for tasks to load
    await screen.findByText("Test Task 1");
    expect(screen.getByText("Test Task 2")).toBeInTheDocument();

    // Filter to active tasks only
    await user.click(screen.getByRole("button", { name: "Active" }));
    expect(screen.getByText("Test Task 1")).toBeInTheDocument();
    expect(screen.queryByText("Test Task 2")).not.toBeInTheDocument();

    // Filter to completed tasks only
    await user.click(screen.getByRole("button", { name: "Completed" }));
    expect(screen.queryByText("Test Task 1")).not.toBeInTheDocument();
    expect(screen.getByText("Test Task 2")).toBeInTheDocument();

    // Back to all tasks
    await user.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getByText("Test Task 1")).toBeInTheDocument();
    expect(screen.getByText("Test Task 2")).toBeInTheDocument();
  });

  it("searches tasks by title and description", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<HomePage />);

    // Wait for tasks to load
    await screen.findByText("Test Task 1");
    expect(screen.getByText("Test Task 2")).toBeInTheDocument();

    // Search by title
    const searchInput = screen.getByPlaceholderText("Search tasks...");
    await user.type(searchInput, "Task 1");

    expect(screen.getByText("Test Task 1")).toBeInTheDocument();
    expect(screen.queryByText("Test Task 2")).not.toBeInTheDocument();

    // Clear search
    await user.clear(searchInput);

    // Search by description
    await user.type(searchInput, "description");
    expect(screen.getByText("Test Task 1")).toBeInTheDocument();
    expect(screen.queryByText("Test Task 2")).not.toBeInTheDocument();
  });

  it("shows appropriate empty states", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<HomePage />);

    // Wait for tasks to load
    await screen.findByText("Test Task 1");

    // Search for something that doesn't exist
    const searchInput = screen.getByPlaceholderText("Search tasks...");
    await user.type(searchInput, "nonexistent task");

    // Should show filtered empty state
    expect(screen.getByText("No tasks match your filter")).toBeInTheDocument();
    expect(
      screen.getByText("Try adjusting your search or filter"),
    ).toBeInTheDocument();
  });

  it("validates new task form", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<HomePage />);

    // Wait for initial load
    await screen.findByText("Test Task 1");

    // Open add task dialog
    await user.click(screen.getByRole("button", { name: /add task/i }));

    // Try to submit without title
    const addButton = screen.getByRole("button", { name: "Add Task" });
    expect(addButton).toBeDisabled();

    // Add title and button should be enabled
    await user.type(screen.getByPlaceholderText("Task title"), "Valid Task");
    expect(addButton).toBeEnabled();
  });
});
