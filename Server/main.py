"""Public entry point for the blogging agent server."""

from Server.services.blog_job_service import get_blog_job_service

if __name__ == "__main__":
    service = get_blog_job_service()
    job_id = service.run(
        "Can you write a blog about different design patterns in Agentic AI?"
    )
    job = service.get_job(job_id)
    print(f"Job {job_id}: {job}")
