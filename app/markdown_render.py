"""REC/IMPL의 서술형 텍스트를 HTML로 렌더링.

REC.content/necessity는 core/parse/fill_rec_csv.py의 escape_markdown()이 CSV 한 줄에
담으려고 실제 개행을 리터럴 "\\n"으로, 목록 "-"를 "\\-"로 이스케이프해뒀으므로 먼저
원상복구한다. IMPL.status/plan은 이 이스케이프를 거치지 않지만(scripts/load_impl.py는
JSON을 그대로 넣음), 해당 없는 문자열에 대한 치환은 no-op이라 같은 함수를 그대로 쓴다.
"""
import markdown as _markdown


def render_markdown(text: str | None) -> str | None:
    if not text:
        return None
    unescaped = text.replace("\\n", "\n").replace("\\-", "-")
    return _markdown.markdown(unescaped, extensions=["nl2br"])
