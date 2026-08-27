import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BlogForm from "../components/BlogForm.jsx";

function setup(props = {}) {
  const defaults = { onSubmit: vi.fn(), busy: false };
  return render(<BlogForm {...defaults} {...props} />);
}

describe("BlogForm", () => {
  it("renders a textarea and submit button", () => {
    setup();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate blog/i })).toBeInTheDocument();
  });

  it("submit button is disabled when topic is empty", () => {
    setup();
    expect(screen.getByRole("button", { name: /generate blog/i })).toBeDisabled();
  });

  it("submit button is disabled when busy=true", () => {
    setup({ busy: true });
    expect(screen.getByRole("button", { name: /starting/i })).toBeDisabled();
  });

  it("does not show error before field is touched", async () => {
    setup();
    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "abc");
    // No blur yet — error should not appear
    expect(screen.queryByText(/at least/i)).not.toBeInTheDocument();
  });

  it("shows error after blur when topic is too short after trimming", async () => {
    setup();
    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "short");
    await userEvent.tab(); // triggers blur
    expect(screen.getByText(/at least/i)).toBeInTheDocument();
  });

  it("shows error when topic is empty and form is submitted", () => {
    setup();
    // Button is disabled on empty input, so submit the form element directly
    const form = screen.getByRole("button", { name: /generate blog/i }).closest("form");
    fireEvent.submit(form);
    expect(screen.getByText(/please enter a topic/i)).toBeInTheDocument();
  });

  it("calls onSubmit with trimmed topic on valid submit", async () => {
    const onSubmit = vi.fn();
    setup({ onSubmit });
    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "  A valid blog topic here  ");
    await userEvent.click(screen.getByRole("button", { name: /generate blog/i }));
    expect(onSubmit).toHaveBeenCalledWith("A valid blog topic here");
  });

  it("submit button is enabled for a valid topic", async () => {
    setup();
    await userEvent.type(screen.getByRole("textbox"), "A valid topic of sufficient length");
    expect(screen.getByRole("button", { name: /generate blog/i })).not.toBeDisabled();
  });

  it("character counter shows current count", async () => {
    setup();
    await userEvent.type(screen.getByRole("textbox"), "hello world");
    expect(screen.getByText(/11 \/ 2000/)).toBeInTheDocument();
  });

  it("counter has warn class near the limit", () => {
    setup();
    const longText = "a".repeat(1810); // > 90% of 2000
    // Use fireEvent.change to set value in one shot; userEvent.type fires 1810 events and times out
    fireEvent.change(screen.getByRole("textbox"), { target: { value: longText } });
    const counter = screen.getByText(/1810 \/ 2000/);
    expect(counter).toHaveClass("warn");
  });
});
