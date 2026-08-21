import pytest

from Server.nodes.synthesizer import _research_banner, _safe_filename, synthesizer
from Server.state import Bullet, Plan, Task


def make_plan(coverage="sufficient", note="") -> Plan:
    return Plan(
        blog_title="Test Blog",
        blog_description="desc",
        evidence_coverage=coverage,
        research_note=note,
        tasks=[
            Task(
                id=1,
                title="Section",
                description="d",
                goal="g",
                bullets=[
                    Bullet(text="b1", bullet_type="prose"),
                    Bullet(text="b2", bullet_type="prose"),
                ],
                target_words=150,
            )
        ],
        audience="developers",
    )


class TestSafeFilename:
    def test_lowercases_title(self):
        assert _safe_filename("My Blog Post") == "my_blog_post.md"

    def test_replaces_spaces_with_underscores(self):
        assert _safe_filename("hello world") == "hello_world.md"

    def test_strips_forbidden_chars(self):
        result = _safe_filename('blog:<>"/\\|?*title')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_truncates_slug_to_200_chars(self):
        long_title = "a" * 300
        result = _safe_filename(long_title)
        # slug[:200] = 200 chars + ".md" = 203 chars total
        assert len(result) == 203

    def test_appends_md_extension(self):
        result = _safe_filename("test blog")
        assert result.endswith(".md")


class TestResearchBanner:
    def test_empty_on_sufficient_no_note(self):
        plan = make_plan(coverage="sufficient", note="")
        assert _research_banner(plan) == ""

    def test_includes_note_on_partial_with_note(self):
        plan = make_plan(coverage="partial", note="Some sections lack sources")
        banner = _research_banner(plan)
        assert "Some sections lack sources" in banner
        assert "partial" in banner

    def test_includes_note_on_insufficient_with_note(self):
        plan = make_plan(coverage="insufficient", note="Very few sources found")
        banner = _research_banner(plan)
        assert "Very few sources found" in banner

    def test_default_banner_on_insufficient_no_note(self):
        plan = make_plan(coverage="insufficient", note="")
        banner = _research_banner(plan)
        assert "insufficient" in banner.lower()
        assert len(banner) > 0

    def test_default_banner_on_partial_no_note(self):
        plan = make_plan(coverage="partial", note="")
        banner = _research_banner(plan)
        assert "partial" in banner.lower()
        assert len(banner) > 0


class TestSynthesizer:
    def test_writes_file_and_returns_final_blog(self, tmp_path, mocker):
        mocker.patch(
            "Server.nodes.synthesizer.blog_output_path",
            return_value=tmp_path / "test_blog.md",
        )
        plan = make_plan(coverage="sufficient", note="")
        state = {
            "plan": plan,
            "sections": ["## Section 1\n\nContent here."],
        }
        result = synthesizer(state)
        assert "final_blog" in result
        assert "# Test Blog" in result["final_blog"]
        assert "Content here." in result["final_blog"]
        assert (tmp_path / "test_blog.md").exists()

    def test_includes_research_banner_when_coverage_partial(self, tmp_path, mocker):
        mocker.patch(
            "Server.nodes.synthesizer.blog_output_path",
            return_value=tmp_path / "test.md",
        )
        plan = make_plan(coverage="partial", note="")
        state = {"plan": plan, "sections": ["## Section\n\nContent."]}
        result = synthesizer(state)
        assert "partial" in result["final_blog"].lower()

    def test_empty_sections_produces_title_only_body(self, tmp_path, mocker):
        mocker.patch(
            "Server.nodes.synthesizer.blog_output_path",
            return_value=tmp_path / "test.md",
        )
        plan = make_plan(coverage="sufficient", note="")
        state = {"plan": plan, "sections": []}
        result = synthesizer(state)
        assert "# Test Blog" in result["final_blog"]
