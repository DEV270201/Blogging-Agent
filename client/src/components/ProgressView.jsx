import { STAGES, stageIndex } from "../stages.js";

export default function ProgressView({ job, onRetry, onBack }) {
  const failed = job.status === "FAILED";

  if (failed) {
    return (
      <div className="progress-card fade-in">
        <div className="halted-icon">⚠️</div>
        <h2>We couldn't generate your blog</h2>
        <p className="progress-topic">“{job.topic}”</p>
        <p className="halted-text">
          Something went wrong due to an unexpected error. Please try again
          shortly.
        </p>
        <div className="halted-actions">
          <button className="ghost-btn" onClick={onBack}>
            Start a new blog
          </button>
        </div>
      </div>
    );
  }

  const halted = job.status === "HALTED";

  if (halted) {
    return (
      <div className="progress-card fade-in">
        <div className="halted-icon">🛑</div>
        <h2>Generation was interrupted</h2>
        <p className="progress-topic">“{job.topic}”</p>
        <p className="halted-text">
          Something went wrong partway through. The good news: the research was
          saved, so you can pick up right where it stopped.
        </p>
        <div className="halted-actions">
          {job.recoverable && (
            <button className="primary-btn" onClick={() => onRetry(job)}>
              ↻ Retry generation
            </button>
          )}
          <button className="ghost-btn" onClick={onBack}>
            Start a new blog
          </button>
        </div>
      </div>
    );
  }

  const current = stageIndex(job.stage);

  return (
    <div className="progress-card fade-in">
      <div className="orb">
        <span className="orb-emoji">{STAGES[current]?.emoji || "✨"}</span>
      </div>
      <h2>Crafting your blog</h2>
      <p className="progress-topic">“{job.topic}”</p>
      <p className="progress-blurb">
        {STAGES[current]?.blurb}
        <span className="dots">
          <span>.</span>
          <span>.</span>
          <span>.</span>
        </span>
      </p>

      <ol className="stepper">
        {STAGES.map((stage, i) => {
          const state =
            i < current ? "done" : i === current ? "current" : "todo";
          return (
            <li key={stage.key} className={`step ${state}`}>
              <span className="step-icon">
                {state === "done" ? "✓" : state === "current" ? (
                  <span className="spinner" />
                ) : (
                  i + 1
                )}
              </span>
              <span className="step-label">{stage.label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
