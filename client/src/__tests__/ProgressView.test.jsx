import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProgressView from "../components/ProgressView.jsx";

const sampleJob = (overrides = {}) => ({
  id: "job-1",
  topic: "Test topic",
  status: "IN-PROGRESS",
  stage: "researching",
  recoverable: false,
  ...overrides,
});

describe("ProgressView — FAILED state", () => {
  it("shows failure heading", () => {
    render(
      <ProgressView
        job={sampleJob({ status: "FAILED" })}
        review={null}
        connectionLost={false}
        onRetry={vi.fn()}
        onDecision={vi.fn()}
        onBack={vi.fn()}
      />
    );
    expect(screen.getByText(/couldn't generate/i)).toBeInTheDocument();
  });
});

describe("ProgressView — HALTED state", () => {
  it("shows interrupted heading", () => {
    render(
      <ProgressView
        job={sampleJob({ status: "HALTED", recoverable: false })}
        review={null}
        connectionLost={false}
        onRetry={vi.fn()}
        onDecision={vi.fn()}
        onBack={vi.fn()}
      />
    );
    expect(screen.getByText(/generation was interrupted/i)).toBeInTheDocument();
  });

  it("shows retry button when job is recoverable", () => {
    render(
      <ProgressView
        job={sampleJob({ status: "HALTED", recoverable: true })}
        review={null}
        connectionLost={false}
        onRetry={vi.fn()}
        onDecision={vi.fn()}
        onBack={vi.fn()}
      />
    );
    expect(screen.getByRole("button", { name: /retry generation/i })).toBeInTheDocument();
  });

  it("does not show retry button when not recoverable", () => {
    render(
      <ProgressView
        job={sampleJob({ status: "HALTED", recoverable: false })}
        review={null}
        connectionLost={false}
        onRetry={vi.fn()}
        onDecision={vi.fn()}
        onBack={vi.fn()}
      />
    );
    expect(screen.queryByRole("button", { name: /retry generation/i })).not.toBeInTheDocument();
  });
});

describe("ProgressView — connection lost", () => {
  it("shows connection lost message", () => {
    render(
      <ProgressView
        job={sampleJob()}
        review={null}
        connectionLost={true}
        onRetry={vi.fn()}
        onDecision={vi.fn()}
        onBack={vi.fn()}
      />
    );
    expect(screen.getByText(/lost contact with the server/i)).toBeInTheDocument();
  });
});

describe("ProgressView — AWAITING_INPUT state (ResearchReview)", () => {
  const reviewPayload = {
    coverage: "partial",
    title: "Test Blog",
    sections: [{ title: "Section 1", goal: "Understand X" }],
    research_note: "",
    evidence_count: 2,
    attempts: 0,
    max_attempts: 2,
    sources: [],
  };

  it("shows the research review component", () => {
    render(
      <ProgressView
        job={sampleJob({ status: "AWAITING_INPUT" })}
        review={reviewPayload}
        connectionLost={false}
        onRetry={vi.fn()}
        onDecision={vi.fn()}
        onBack={vi.fn()}
      />
    );
    expect(screen.getByText(/review the research/i)).toBeInTheDocument();
  });

  it("shows coverage label and evidence count", () => {
    render(
      <ProgressView
        job={sampleJob({ status: "AWAITING_INPUT" })}
        review={reviewPayload}
        connectionLost={false}
        onRetry={vi.fn()}
        onDecision={vi.fn()}
        onBack={vi.fn()}
      />
    );
    expect(screen.getByText(/limited sources/i)).toBeInTheDocument();
    expect(screen.getByText(/2 sources/i)).toBeInTheDocument();
  });

  it("calls onDecision with 'proceed' when Proceed button clicked", async () => {
    const onDecision = vi.fn();
    render(
      <ProgressView
        job={sampleJob({ status: "AWAITING_INPUT" })}
        review={reviewPayload}
        connectionLost={false}
        onRetry={vi.fn()}
        onDecision={onDecision}
        onBack={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /proceed/i }));
    expect(onDecision).toHaveBeenCalledWith(expect.anything(), "proceed");
  });

  it("calls onDecision with 'redo' when Research again clicked", async () => {
    const onDecision = vi.fn();
    render(
      <ProgressView
        job={sampleJob({ status: "AWAITING_INPUT" })}
        review={reviewPayload}
        connectionLost={false}
        onRetry={vi.fn()}
        onDecision={onDecision}
        onBack={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /research again/i }));
    expect(onDecision).toHaveBeenCalledWith(expect.anything(), "redo");
  });

  it("shows last-round warning when at cap", () => {
    render(
      <ProgressView
        job={sampleJob({ status: "AWAITING_INPUT" })}
        review={{ ...reviewPayload, attempts: 1, max_attempts: 2 }}
        connectionLost={false}
        onRetry={vi.fn()}
        onDecision={vi.fn()}
        onBack={vi.fn()}
      />
    );
    expect(screen.getByText(/last re-research round/i)).toBeInTheDocument();
  });
});

describe("ProgressView — IN-PROGRESS state", () => {
  it("renders the stage stepper with correct structure", () => {
    render(
      <ProgressView
        job={sampleJob({ status: "IN-PROGRESS", stage: "researching" })}
        review={null}
        connectionLost={false}
        onRetry={vi.fn()}
        onDecision={vi.fn()}
        onBack={vi.fn()}
      />
    );
    expect(screen.getByText(/crafting your blog/i)).toBeInTheDocument();
    // Should have list items for the stepper
    const stepItems = screen.getAllByRole("listitem");
    expect(stepItems.length).toBeGreaterThan(0);
  });
});
