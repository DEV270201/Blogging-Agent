import { STAGES, stageIndex } from "../stages.js";

const COVERAGE_COPY = {
  partial: {
    label: "Limited sources",
    text: "We found some sources, but not enough to fully back every section. The blog will lean on general guidance where evidence is thin.",
  },
  insufficient: {
    label: "Very little evidence",
    text: "We couldn't find solid sources for this topic. The blog would be mostly general guidance rather than well-cited facts.",
  },
};

// The stepper paused right before drafting: planning is done, writing_sections
// is the pause point, everything after is still to-do.
function ReviewStepper() {
  const planningIdx = stageIndex("planning");
  return (
    <ol className="stepper">
      {STAGES.map((stage, i) => {
        let state = "todo";
        if (stage.key === "writing_sections") state = "paused";
        else if (i <= planningIdx) state = "done";
        return (
          <li key={stage.key} className={`step ${state}`}>
            <span className="step-icon">
              {state === "done" ? "✓" : state === "paused" ? "⏸" : i + 1}
            </span>
            <span className="step-label">{stage.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function ResearchReview({ job, review, onDecision }) {
  const coverage = review?.coverage;
  const copy = COVERAGE_COPY[coverage] || {
    label: "Limited research",
    text: "The research came back thin. Review the plan below and decide how to proceed.",
  };
  const lastRound =
    review && review.attempts + 1 >= review.max_attempts;

  return (
    <div className="progress-card fade-in">
      <ReviewStepper />

      <div className="review-icon">🧐</div>
      <h2>Review the research before we write</h2>
      <p className="progress-topic">“{job.topic}”</p>

      {!review ? (
        <p className="progress-blurb">Loading the plan…</p>
      ) : (
        <>
          <div className={`review-coverage ${coverage || ""}`}>
            <span className="review-coverage-label">⚠ {copy.label}</span>
            <span className="review-coverage-count">
              {review.evidence_count} source
              {review.evidence_count === 1 ? "" : "s"} found
            </span>
          </div>
          <p className="review-note">{review.research_note || copy.text}</p>

          {review.title && (
            <div className="review-plan">
              <div className="review-plan-title">{review.title}</div>
              <ul className="review-sections">
                {review.sections.map((s, i) => (
                  <li key={i}>
                    <span className="review-section-title">{s.title}</span>
                    {s.goal && (
                      <span className="review-section-goal">{s.goal}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {review.sources.length > 0 && (
            <div className="review-sources">
              <div className="review-sources-head">Sources</div>
              <ul>
                {review.sources.map((src, i) => (
                  <li key={i}>
                    <a href={src.url} target="_blank" rel="noreferrer">
                      {src.title || src.url}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="halted-actions">
            <button
              className="primary-btn"
              onClick={() => onDecision(job, "proceed")}
            >
              Proceed with limited research
            </button>
            <button
              className="ghost-btn"
              onClick={() => onDecision(job, "redo")}
            >
              ↻ Research again
            </button>
          </div>
          {lastRound && (
            <p className="review-hint">
              This is the last re-research round — after this we'll write with
              whatever we find.
            </p>
          )}
        </>
      )}
    </div>
  );
}

export default function ProgressView({
  job,
  review,
  connectionLost,
  onRetry,
  onDecision,
  onBack,
}) {
  if (connectionLost) {
    return (
      <div className="progress-card fade-in">
        <div className="halted-icon">📡</div>
        <h2>We've lost contact with the server</h2>
        <p className="progress-topic">“{job.topic}”</p>
        <p className="halted-text">
          We can no longer reach the server, so this generation can't be tracked
          right now. It may have been interrupted. Check your library — if it was recoverable, you'll find it in the
          Recoverable tab.
        </p>
        <div className="halted-actions">
          <button className="ghost-btn" onClick={onBack}>
            Start a new blog
          </button>
        </div>
      </div>
    );
  }

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

  if (job.status === "AWAITING_INPUT") {
    return <ResearchReview job={job} review={review} onDecision={onDecision} />;
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
