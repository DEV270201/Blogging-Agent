import re
from Server.config import BLOGS_DIR
from Server.state import BlogState

def _safe_filename(title: str) -> str:
    slug = title.lower().replace(" ", "_")
    slug = re.sub(r'[<>:"/\\|?*]', "", slug)
    return slug[:200] + ".md"  # optional length cap

def synthesizer(state: BlogState) -> BlogState:
    print(f"Synthesizing blog......")
    
    title = state["plan"].blog_title
    body = "\n\n".join(state["sections"]).strip()

    final_md = f"# {title}\n\n{body}\n"

    # ---- save to file ----
    filename = _safe_filename(title)
    output_path = BLOGS_DIR / filename
    output_path.write_text(final_md, encoding="utf-8")

    return {"final_blog": final_md}