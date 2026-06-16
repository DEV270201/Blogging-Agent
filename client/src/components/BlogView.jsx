import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { formatDate } from "../stages.js";

export default function BlogView({ blog, job, loading }) {
  const [copied, setCopied] = useState(false);

  if (loading) {
    return (
      <div className="blog-view">
        <div className="skeleton skeleton-title" />
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line short" />
      </div>
    );
  }

  if (!blog) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(blog.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable — ignore */
    }
  };

  return (
    <div className="blog-view fade-in">
      <div className="blog-toolbar">
        <div>
          {job?.created_at && (
            <span className="blog-meta">Generated {formatDate(job.created_at)}</span>
          )}
        </div>
        <button className="ghost-btn small" onClick={handleCopy}>
          {copied ? "Copied ✓" : "Copy markdown"}
        </button>
      </div>

      <article className="markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{blog.content}</ReactMarkdown>
      </article>
    </div>
  );
}
