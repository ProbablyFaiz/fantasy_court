// frontend/src/test/mocks/handlers.ts
import { HttpResponse, http } from "msw";
import { type TaskListItem, TaskPriority, type TaskUpdate } from "@/client";
import type { TaskCreate } from "@/client/types.gen";

const mockTasks: TaskListItem[] = [
  {
    id: 1,
    title: "Test Task 1",
    description: "Test description",
    completed: false,
    priority: TaskPriority.MEDIUM,
    created_at: new Date(),
    updated_at: new Date(),
  },
  {
    id: 2,
    title: "Test Task 2",
    description: null,
    completed: true,
    priority: TaskPriority.HIGH,
    created_at: new Date(),
    updated_at: new Date(),
  },
];

export const handlers = [
  // GET /api/tasks
  http.get("/api/tasks", () => {
    return HttpResponse.json({
      items: mockTasks,
      total: mockTasks.length,
      page: 1,
      size: 10,
      pages: 1,
    });
  }),

  // POST /api/tasks
  http.post("/api/tasks", async ({ request }) => {
    const task = (await request.json()) as TaskCreate;
    const newTask = {
      id: Math.max(...mockTasks.map((t) => t.id)) + 1,
      ...(task as TaskCreate),
      completed: false,
      created_at: new Date(),
      updated_at: new Date(),
    };
    return HttpResponse.json(newTask, { status: 201 });
  }),

  // PUT /api/tasks/:id
  http.put("/api/tasks/:id", async ({ params, request }) => {
    const id = Number(params.id);
    const updates = (await request.json()) as TaskUpdate;
    const task = mockTasks.find((t) => t.id === id);

    if (!task) {
      return new HttpResponse(null, { status: 404 });
    }

    const updatedTask = {
      ...task,
      ...updates,
      updated_at: new Date(),
    };
    return HttpResponse.json(updatedTask);
  }),

  // DELETE /api/tasks/:id
  http.delete("/api/tasks/:id", ({ params }) => {
    const id = Number(params.id);
    const index = mockTasks.findIndex((t) => t.id === id);

    if (index === -1) {
      return new HttpResponse(null, { status: 404 });
    }

    return new HttpResponse(null, { status: 204 });
  }),
];
