// 피드백 textarea를 EasyMDE(마크다운 문법 에디터)로 강화한다. 저장되는 값은 여전히
// 순수 마크다운 텍스트라 백엔드(render_feedback_markdown)는 그대로 — textarea만 교체.
function createEditor(el) {
  if (el.classList.contains('md-editor-ready')) return;
  el.classList.add('md-editor-ready');
  var editor = new EasyMDE({
    element: el,
    spellChecker: false,
    status: false,
    // EasyMDE의 자체 미리보기는 marked.js로 렌더링하는데, 실제 화면은 서버의
    // python-markdown(render_feedback_markdown)으로 렌더링돼서 규칙이 미묘하게
    // 다르다(예: 목록 앞 빈 줄 요구사항) — 둘이 안 맞아서 오히려 혼란스러우니 뺀다.
    toolbar: ['bold', 'italic', 'unordered-list'],
    placeholder: el.getAttribute('placeholder') || '',
  });

  // EasyMDE는 원본 textarea를 display:none으로 숨기는데, required가 남아있으면
  // 브라우저가 검증 실패 시 그 (숨겨진) textarea에 포커스를 주려다
  // "not focusable" 에러를 내며 제출 자체를 막아버린다. required는 떼어내고,
  // 빈 값 체크는 여기서 화면에 보이는 에디터를 대상으로 직접 한다.
  el.required = false;
  var form = el.closest('form');
  if (form) {
    form.addEventListener('submit', function (e) {
      if (!editor.value().trim()) {
        e.preventDefault();
        editor.codemirror.focus();
      }
    });
  }
  return editor;
}

// 수정 폼은 htmx가 통째로 새로 그려 넣으므로, 스왑될 때마다 새로 들어온 textarea를
// 다시 찾아서 초기화해야 한다(이미 초기화된 건 위 md-editor-ready 클래스로 걸러짐).
// 새로 등록하는 폼은 여기서 자동 초기화하지 않는다 — 아래 토글 로직 참고.
function initFeedbackEditors(root) {
  (root || document).querySelectorAll('textarea.md-editor:not(.md-editor-ready)').forEach(createEditor);
}

document.body.addEventListener('htmx:afterSwap', function () {
  initFeedbackEditors();
});

// "새 피드백 작성" 폼은 기본적으로 접어두고 "+ 피드백 달기" 버튼을 눌렀을 때만 펼친다
// (그냥 읽기만 할 땐 큰 흰 박스가 항상 떠 있을 필요가 없어서). CodeMirror는
// display:none인 상태에서 초기화하면 높이 계산이 깨지므로, 펼쳐지는 시점에 처음으로
// 에디터를 만든다(지연 초기화) — 그 전까진 el.md-editor-ready 클래스가 안 붙어있다.
document.addEventListener('click', function (e) {
  var toggle = e.target.closest('.feedback-toggle');
  if (toggle) {
    var form = document.getElementById(toggle.dataset.form);
    if (!form) return;
    toggle.hidden = true;
    form.style.display = '';
    var textarea = form.querySelector('textarea.md-editor');
    if (textarea) createEditor(textarea);
    return;
  }

  var cancel = e.target.closest('.feedback-cancel');
  if (cancel) {
    var cform = cancel.closest('form');
    if (!cform) return;
    cform.style.display = 'none';
    var toggleBtn = document.getElementById(cform.dataset.toggle);
    if (toggleBtn) toggleBtn.hidden = false;
    return;
  }

  // 근거 링크 행 추가/삭제. <template>에서 매번 복제해서 만들기 때문에 남은 행이
  // 0개여도(전부 삭제해도) "+ 링크 추가"가 계속 정상 동작한다.
  var addBtn = e.target.closest('.evidence-add');
  if (addBtn) {
    var field = addBtn.closest('.evidence-field');
    var tpl = field && field.querySelector('.evidence-row-template');
    if (!tpl) return;
    var newRow = tpl.content.firstElementChild.cloneNode(true);
    field.querySelector('.evidence-rows').appendChild(newRow);
    newRow.querySelector('input').focus();
    return;
  }

  var removeBtn = e.target.closest('.evidence-remove');
  if (removeBtn) {
    removeBtn.closest('.evidence-row').remove();
  }
});
