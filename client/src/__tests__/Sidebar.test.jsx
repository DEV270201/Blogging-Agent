import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Sidebar from "../components/Sidebar.jsx";

function makeJob(overrides = {}) {
  return {
    id: `job-${Math.random()}`,
    topic: "Test blog topic",
    status: "COMPLETE",
    stage: "complete",
    recoverable: false,
    created_at: "2026-08-21T12:00:00.000Z",
    ...overrides,
  };
}

function setup(props = {}) {
  const defaults = {
    jobs: [],
    tab: "library",
    setTab: vi.fn(),
    activeJobId: null,
    onSelect: vi.fn(),
    onRetry: vi.fn(),
    onNew: vi.fn(),
    serverOk: true,
  };
  return render(<Sidebar {...defaults} {...props} />);
}

describe("Sidebar — tab filtering", () => {
  it("library tab shows IN-PROGRESS and COMPLETE jobs", () => {
    const jobs = [
      makeJob({ status: "IN-PROGRESS" }),
      makeJob({ status: "COMPLETE" }),
      makeJob({ status: "HALTED", recoverable: true }),
      makeJob({ status: "AWAITING_INPUT" }),
    ];
    setup({ jobs, tab: "library" });
    const cards = screen.getAllByRole("button", { name: /test blog topic/i });
    // Library excludes HALTED and AWAITING_INPUT
    expect(cards).toHaveLength(2);
  });

  it("needsInput tab shows only AWAITING_INPUT jobs", () => {
    const jobs = [
      makeJob({ status: "COMPLETE" }),
      makeJob({ status: "AWAITING_INPUT" }),
      makeJob({ status: "AWAITING_INPUT" }),
    ];
    setup({ jobs, tab: "needsInput" });
    const cards = screen.getAllByRole("button", { name: /test blog topic/i });
    expect(cards).toHaveLength(2);
  });

  it("recoverable tab shows only HALTED+recoverable jobs", () => {
    const jobs = [
      makeJob({ status: "COMPLETE" }),
      makeJob({ status: "HALTED", recoverable: true }),
      makeJob({ status: "HALTED", recoverable: false }),
    ];
    setup({ jobs, tab: "recoverable" });
    const cards = screen.getAllByRole("button", { name: /test blog topic/i });
    expect(cards).toHaveLength(1);
  });

  it("shows empty message when library is empty", () => {
    setup({ jobs: [], tab: "library" });
    expect(screen.getByText(/no blogs yet/i)).toBeInTheDocument();
  });

  it("shows empty message when needsInput is empty", () => {
    setup({ jobs: [], tab: "needsInput" });
    expect(screen.getByText(/nothing waiting on you/i)).toBeInTheDocument();
  });

  it("shows empty message when recoverable is empty", () => {
    setup({ jobs: [], tab: "recoverable" });
    expect(screen.getByText(/nothing to recover/i)).toBeInTheDocument();
  });
});

describe("Sidebar — job card interactions", () => {
  it("clicking a job card calls onSelect with that job", async () => {
    const onSelect = vi.fn();
    const job = makeJob({ status: "COMPLETE" });
    setup({ jobs: [job], tab: "library", onSelect });
    await userEvent.click(screen.getByRole("button", { name: /test blog topic/i }));
    expect(onSelect).toHaveBeenCalledWith(job);
  });

  it("retry button calls onRetry (not onSelect)", async () => {
    const onSelect = vi.fn();
    const onRetry = vi.fn();
    const job = makeJob({ status: "HALTED", recoverable: true });
    setup({ jobs: [job], tab: "recoverable", onSelect, onRetry });
    await userEvent.click(screen.getByText(/↻ Retry/));
    expect(onRetry).toHaveBeenCalledWith(job);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("retry button is shown on recoverable tab", () => {
    const job = makeJob({ status: "HALTED", recoverable: true });
    setup({ jobs: [job], tab: "recoverable" });
    expect(screen.getByText(/↻ Retry/)).toBeInTheDocument();
  });

  it("retry button is not shown on library tab", () => {
    const job = makeJob({ status: "COMPLETE" });
    setup({ jobs: [job], tab: "library" });
    expect(screen.queryByText(/↻ Retry/)).not.toBeInTheDocument();
  });
});

describe("Sidebar — server status", () => {
  it("shows Server online when serverOk=true", () => {
    setup({ serverOk: true });
    expect(screen.getByText(/server online/i)).toBeInTheDocument();
  });

  it("shows Server offline when serverOk=false", () => {
    setup({ serverOk: false });
    expect(screen.getByText(/server offline/i)).toBeInTheDocument();
  });

  it("shows Connecting when serverOk=null", () => {
    setup({ serverOk: null });
    expect(screen.getByText(/connecting/i)).toBeInTheDocument();
  });
});

describe("Sidebar — library tab badge", () => {
  it("shows the count of library jobs in the tab badge", () => {
    const jobs = [makeJob({ status: "COMPLETE" }), makeJob({ status: "IN-PROGRESS" })];
    setup({ jobs, tab: "library" });
    // The Library tab badge should show 2
    expect(screen.getByText("2")).toBeInTheDocument();
  });
});
