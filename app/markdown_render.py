"""REC/IMPL의 서술형 텍스트를 HTML로 렌더링.

REC.content/necessity는 core/parse/fill_rec_csv.py의 escape_markdown()이 CSV 한 줄에
담으려고 실제 개행을 리터럴 "\\n"으로, 목록 "-"를 "\\-"로 이스케이프해뒀으므로 먼저
원상복구한다. IMPL.status/plan은 이 이스케이프를 거치지 않지만(scripts/load_impl.py는
JSON을 그대로 넣음), 해당 없는 문자열에 대한 치환은 no-op이라 같은 함수를 그대로 쓴다.
"""
import html as _html

import markdown as _markdown


def render_markdown(text: str | None) -> str | None:
    if not text:
        return None
    unescaped = text.replace("\\n", "\n").replace("\\-", "-")
    return _markdown.markdown(unescaped, extensions=["nl2br", "tables"])


def render_feedback_markdown(text: str | None) -> str | None:
    """FEEDBACK.content는 로그인한 사용자 누구나 직접 입력하는 값이라, REC/IMPL과 달리
    신뢰할 수 없다. python-markdown은 raw HTML을 그대로 통과시키므로, 마크다운 문법
    (**, -)은 안 건드리면서 <, > 등만 먼저 escape해 저장형 XSS를 막는다."""
    if not text:
        return None
    return _markdown.markdown(_html.escape(text), extensions=["nl2br", "tables"])
