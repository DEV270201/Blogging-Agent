CREATE TABLE IF NOT EXISTS blog_jobs (
    id UUID PRIMARY KEY,
    topic TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'IN-PROGRESS'
        CHECK (status IN ('IN-PROGRESS', 'COMPLETE', 'HALTED')),
    stage TEXT NOT NULL DEFAULT 'queued',
    recoverable BOOLEAN NOT NULL DEFAULT FALSE,
    research_done BOOLEAN NOT NULL DEFAULT FALSE,
    final_blog_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure the stage column exists on databases created before it was added.
ALTER TABLE blog_jobs ADD COLUMN IF NOT EXISTS stage TEXT NOT NULL DEFAULT 'queued';
