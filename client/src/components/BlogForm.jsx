import { useState } from "react";

import { TOPIC_MIN, TOPIC_MAX } from "../api.js";

export default function BlogForm({ onSubmit, busy }) {
  const [topic, setTopic] = useState("");
  const [touched, setTouched] = useState(false);

  const trimmedLen = topic.trim().length;
  const charCount = topic.length;
  const wordCount = topic.trim() ? topic.trim().split(/\s+/).length : 0;

  // Client-side validation mirrors the server rules (10–2000 chars, trimmed).
  let error = null;
  if (trimmedLen === 0) error = "Please enter a topic.";
  else if (trimmedLen < TOPIC_MIN)
    error = `Add a little more detail — at least ${TOPIC_MIN} characters.`;
  else if (charCount > TOPIC_MAX)
    error = `That's too long — keep it under ${TOPIC_MAX} characters.`;

  const isValid = !error;
  const nearLimit = charCount > TOPIC_MAX * 0.9;

  const handleSubmit = (e) => {
    e.preventDefault();
    setTouched(true);
    if (!isValid || busy) return;
    onSubmit(topic.trim());
  };

  return (
    <div className="create-card fade-in">
      <div className="create-hero">
        <span className="create-spark">✨</span>
        <h1>What should we write about?</h1>
        <p className="create-sub">
          Describe a topic and the AI agent will research the web, plan an
          outline, and draft a cited technical blog for you.
        </p>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <textarea
            className={`topic-input ${touched && error ? "invalid" : ""}`}
            placeholder="e.g. Best practices for deploying LangChain apps to production on AWS"
            value={topic}
            maxLength={TOPIC_MAX}
            rows={4}
            disabled={busy}
            onChange={(e) => setTopic(e.target.value)}
            onBlur={() => setTouched(true)}
          />

          <div className="field-footer">
            <span className="word-count">
              {wordCount} {wordCount === 1 ? "word" : "words"}
            </span>
            <span
              className={`counter ${
                charCount > TOPIC_MAX
                  ? "error"
                  : nearLimit
                  ? "warn"
                  : ""
              }`}
            >
              {charCount} / {TOPIC_MAX}
            </span>
          </div>
        </div>

        {touched && error && <p className="form-error">{error}</p>}

        <button type="submit" className="primary-btn" disabled={!isValid || busy}>
          {busy ? "Starting…" : "Generate blog"}
        </button>
      </form>
    </div>
  );
}
