import { STATUS_META, formatDate } from "../stages.js";

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || { label: status, className: "" };
  return <span className={`badge ${meta.className}`}>{meta.label}</span>;
}

function JobCard({ job, active, onSelect, onRetry, recoverable }) {
  return (
    <button
      className={`job-card ${active ? "active" : ""}`}
      onClick={() => onSelect(job)}
    >
      <div className="job-card-top">
        <StatusBadge status={job.status} />
        <span className="job-date">{formatDate(job.created_at)}</span>
      </div>
      <p className="job-topic">{job.topic}</p>
      {recoverable && (
        <span
          className="retry-btn"
          role="button"
          tabIndex={0}
          onClick={(e) => {
            e.stopPropagation();
            onRetry(job);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.stopPropagation();
              onRetry(job);
            }
          }}
        >
          ↻ Retry
        </span>
      )}
    </button>
  );
}

export default function Sidebar({
  jobs,
  tab,
  setTab,
  activeJobId,
  onSelect,
  onRetry,
  onNew,
  serverOk,
}) {
  const library = jobs.filter((j) => j.status !== "HALTED");
  const recoverable = jobs.filter(
    (j) => j.status === "HALTED" && j.recoverable
  );
  const list = tab === "library" ? library : recoverable;

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-logo">📝</span>
        <div>
          <div className="brand-name">Blog Studio</div>
          <div className="brand-status">
            <span className={`status-dot ${serverOk ? "ok" : "down"}`} />
            {serverOk === null
              ? "Connecting…"
              : serverOk
              ? "Server online"
              : "Server offline"}
          </div>
        </div>
      </div>

      <button className="new-btn" onClick={onNew}>
        + New blog
      </button>

      <div className="tabs">
        <button
          className={`tab ${tab === "library" ? "active" : ""}`}
          onClick={() => setTab("library")}
        >
          Library
          <span className="tab-badge">{library.length}</span>
        </button>
        <button
          className={`tab ${tab === "recoverable" ? "active" : ""}`}
          onClick={() => setTab("recoverable")}
        >
          Recoverable
          {recoverable.length > 0 && (
            <span className="tab-badge alert">{recoverable.length}</span>
          )}
        </button>
      </div>

      <div className="job-list">
        {list.length === 0 ? (
          <div className="empty">
            {tab === "library"
              ? "No blogs yet. Create your first one!"
              : "Nothing to recover — all clear. 🎉"}
          </div>
        ) : (
          list.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              active={job.id === activeJobId}
              onSelect={onSelect}
              onRetry={onRetry}
              recoverable={tab === "recoverable"}
            />
          ))
        )}
      </div>
    </aside>
  );
}
