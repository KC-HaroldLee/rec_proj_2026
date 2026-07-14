// 피드백 textarea에 굵게(**)/기울임(*)/목록(-) 표시만 끼워 넣는 최소 툴바.
// 리치 에디터 라이브러리 없이, 서버가 이미 렌더링하는 markdown 문법에 맞춰 텍스트를 조작한다.
// 수정 폼은 htmx로 통째로 교체되므로 개별 바인딩 대신 document 위임으로 처리.

// 브라우저는 button을 클릭하면 mousedown 시점에 그 button으로 포커스를 옮겨버려서,
// textarea의 선택영역(selectionStart/End)이 버튼 클릭 전에 이미 날아간다. mousedown에서
// 미리 막아 포커스가 계속 textarea에 남아있게 해야 "어디에 삽입할지"가 안 틀어진다.
document.addEventListener('mousedown', function (e) {
  if (e.target.closest('.md-btn')) e.preventDefault();
});

document.addEventListener('click', function (e) {
  var btn = e.target.closest('.md-btn');
  if (!btn) return;
  e.preventDefault();

  var toolbar = btn.closest('.md-toolbar');
  var textarea = toolbar && toolbar.nextElementSibling;
  if (!textarea || textarea.tagName !== 'TEXTAREA') return;

  var start = textarea.selectionStart;
  var end = textarea.selectionEnd;
  var value = textarea.value;
  var selected = value.slice(start, end);
  var replacement, selectStart, selectEnd;

  if (btn.dataset.md === 'bold') {
    var boldText = selected || '굵게';
    replacement = '**' + boldText + '**';
    selectStart = start + 2;
    selectEnd = selectStart + boldText.length;
  } else if (btn.dataset.md === 'italic') {
    var italicText = selected || '기울임';
    replacement = '*' + italicText + '*';
    selectStart = start + 1;
    selectEnd = selectStart + italicText.length;
  } else if (btn.dataset.md === 'list') {
    var items = (selected || '목록 항목').split('\n').map(function (line) {
      return line.indexOf('- ') === 0 ? line : '- ' + line;
    }).join('\n');

    // markdown은 목록 바로 앞에 빈 줄이 없으면 새 블록으로 안 잡고 그냥 텍스트로 취급한다.
    // 문단 중간/줄 끝에서 버튼을 눌러도 목록이 되도록 필요하면 빈 줄을 채워 넣는다.
    var before = value.slice(0, start);
    var prefix = '';
    if (before.length && !/\n\n$/.test(before)) {
      prefix = /\n$/.test(before) ? '\n' : '\n\n';
    }

    replacement = prefix + items;
    selectStart = start + prefix.length;
    selectEnd = selectStart + items.length;
  } else {
    return;
  }

  textarea.value = value.slice(0, start) + replacement + value.slice(end);
  textarea.setSelectionRange(selectStart, selectEnd);
  textarea.focus();
});
