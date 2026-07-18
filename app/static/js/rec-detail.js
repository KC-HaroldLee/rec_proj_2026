// 권고 상세 페이지: 기관 버튼을 누르면 그 기관 블록만 보이는 탭 전환.
// 프레임워크 없이 순수 JS로 — 링크(href="#inst-N")는 그대로 둬서 JS가 꺼져 있어도
// 최소한 스크롤 이동은 되도록(progressive enhancement) 했다.
document.addEventListener('DOMContentLoaded', function () {
  var tabs = document.querySelectorAll('.inst-tab');
  var blocks = document.querySelectorAll('[data-inst-block]');
  if (!tabs.length) return;

  function show(instId) {
    blocks.forEach(function (b) {
      b.style.display = (b.dataset.instBlock === instId) ? '' : 'none';
    });
    tabs.forEach(function (t) {
      t.classList.toggle('active', t.dataset.inst === instId);
    });
  }

  tabs.forEach(function (t) {
    t.addEventListener('click', function (e) {
      e.preventDefault();
      show(t.dataset.inst);
      history.replaceState(null, '', '#inst-' + t.dataset.inst);
    });
  });

  // 피드백 등록/수정 후에는 "#impl-N"으로 리다이렉트되는데(feedback.py),
  // 이 경우에도 해당 impl이 속한 기관 탭이 선택되도록 처리한다.
  var rawHash = (location.hash || '').slice(1);
  var instId, scrollTarget;
  if (rawHash.indexOf('impl-') === 0) {
    var implEl = document.getElementById(rawHash);
    var block = implEl && implEl.closest('[data-inst-block]');
    if (block) {
      instId = block.dataset.instBlock;
      scrollTarget = implEl;
    }
  } else if (rawHash.indexOf('inst-') === 0) {
    instId = rawHash.slice('inst-'.length);
  }
  if (!instId) instId = tabs[0].dataset.inst;

  show(instId);
  if (scrollTarget) scrollTarget.scrollIntoView();
});
