// 渐进增强：核心表单、记录查看和 CSV 导出始终由 Flask 提供。
(() => {
  'use strict';

  const toast = document.getElementById('toast');
  let toastTimer;
  const announce = (message) => {
    if (!toast) return;
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.add('is-visible');
    toastTimer = window.setTimeout(() => toast.classList.remove('is-visible'), 3000);
  };

  document.querySelectorAll('[data-dismiss]').forEach((button) => {
    button.hidden = false;
    button.addEventListener('click', () => {
      const notice = button.closest('.notice');
      const messages = notice.parentElement;
      notice.remove();
      if (!messages.children.length) messages.remove();
    });
  });

  const dialog = document.getElementById('confirm-dialog');
  let pendingForm = null;
  const confirmedForms = new WeakSet();
  const submitButtons = document.querySelectorAll('[data-submit-text]');
  submitButtons.forEach((button) => {
    const label = button.querySelector('.button-label') || button;
    button.dataset.originalText = label.textContent;
  });

  document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (form.dataset.confirm && !confirmedForms.delete(form)) {
        if (dialog && typeof dialog.showModal === 'function') {
          event.preventDefault();
          pendingForm = form;
          document.getElementById('confirm-description').textContent = form.dataset.confirm;
          dialog.showModal();
          return;
        }
        if (!window.confirm(form.dataset.confirm)) {
          event.preventDefault();
          return;
        }
      }
      if (form.getAttribute('aria-busy') === 'true') {
        event.preventDefault();
        return;
      }
      const button = form.querySelector('[data-submit-text]');
      if (button) {
        form.setAttribute('aria-busy', 'true');
        button.disabled = true;
        (button.querySelector('.button-label') || button).textContent = button.dataset.submitText;
      }
    });
  });

  if (dialog) {
    dialog.querySelector('[data-dialog-cancel]').addEventListener('click', () => {
      pendingForm = null;
      dialog.close();
    });
    dialog.querySelector('[data-dialog-confirm]').addEventListener('click', () => {
      const form = pendingForm;
      pendingForm = null;
      dialog.close();
      if (form) {
        confirmedForms.add(form);
        form.requestSubmit();
      }
    });
    dialog.addEventListener('cancel', () => { pendingForm = null; });
    dialog.addEventListener('click', (event) => {
      if (event.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right ||
          event.clientY < bounds.top || event.clientY > bounds.bottom) {
        pendingForm = null;
        dialog.close();
      }
    });
  }

  // 浏览器后退恢复页面时，让表单可以再次提交。
  window.addEventListener('pageshow', () => {
    submitButtons.forEach((button) => {
      button.disabled = false;
      (button.querySelector('.button-label') || button).textContent = button.dataset.originalText;
    });
    document.querySelectorAll('form[aria-busy]').forEach((form) => form.removeAttribute('aria-busy'));
  });

  document.querySelectorAll('[data-toggle-password]').forEach((button) => {
    const input = document.getElementById(button.getAttribute('aria-controls'));
    button.hidden = false;
    button.addEventListener('click', () => {
      const visible = input.type === 'password';
      input.type = visible ? 'text' : 'password';
      button.setAttribute('aria-pressed', String(visible));
      button.setAttribute('aria-label', visible ? '隐藏密码' : '显示密码');
    });
  });

  const cleanCode = (value) => value.normalize('NFKC').replace(/[^0-9]/g, '').slice(0, 6);
  document.querySelectorAll('[data-code-entry]').forEach((entry) => {
    const input = entry.querySelector('input');
    const slots = Array.from(entry.querySelectorAll('.code-slot'));
    entry.querySelector('.code-slots').hidden = false;
    entry.classList.add('is-enhanced');
    const render = () => {
      const value = cleanCode(input.value);
      if (input.value !== value) input.value = value;
      const cursor = Math.min(input.selectionStart ?? value.length, 5);
      slots.forEach((slot, index) => {
        slot.textContent = value[index] || '';
        slot.classList.toggle('is-current', index === cursor);
      });
    };
    ['input', 'focus', 'blur', 'keyup', 'select', 'click'].forEach((event) => input.addEventListener(event, render));
    input.addEventListener('paste', (event) => {
      if (!event.clipboardData) return;
      event.preventDefault();
      const digits = cleanCode(event.clipboardData.getData('text'));
      if (digits.length === 6) {
        input.value = digits;
        input.setSelectionRange(6, 6);
      } else {
        input.setRangeText(digits, input.selectionStart, input.selectionEnd, 'end');
        input.value = input.value.slice(0, 6);
      }
      render();
    });
    render();
  });

  document.querySelectorAll('[data-copy]').forEach((button) => {
    // 无脚本时不显示无法执行的复制按钮。
    button.hidden = false;
    button.addEventListener('click', async () => {
      const value = button.dataset.copy;
      let copied = false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(value);
          copied = true;
        }
      } catch { /* 局域网 HTTP 或浏览器权限不足时使用兼容复制。 */ }
      if (!copied) {
        const field = document.createElement('textarea');
        field.value = value;
        field.setAttribute('readonly', '');
        field.style.cssText = 'position:fixed;left:-9999px;top:0';
        document.body.append(field);
        field.select();
        try { copied = document.execCommand('copy'); } catch { copied = false; }
        field.remove();
        button.focus();
      }
      if (copied) announce(button.dataset.copySuccess || '已复制');
      else window.prompt('请选择并复制以下内容：', value);
    });
  });

  const normalizeSearch = (value) => value.normalize('NFKC').trim().toLocaleLowerCase('zh-CN');
  const sessionItems = Array.from(document.querySelectorAll('[data-session-list] [data-session-state]'));
  const search = document.querySelector('[data-session-search]');
  const filterButtons = document.querySelectorAll('[data-session-filter]');
  let activeFilter = 'all';
  const filterSessions = () => {
    const query = normalizeSearch(search ? search.value : '');
    let visible = 0;
    sessionItems.forEach((item) => {
      const matches = (activeFilter === 'all' || item.dataset.sessionState === activeFilter) &&
        normalizeSearch(item.dataset.searchable).includes(query);
      item.hidden = !matches;
      if (matches) visible++;
    });
    const empty = document.querySelector('[data-list-empty]');
    if (empty) empty.hidden = visible !== 0;
    const count = document.querySelector('[data-list-count]');
    if (count) count.textContent = query || activeFilter !== 'all' ?
      '显示 ' + visible + ' / ' + sessionItems.length + ' 场签到活动' :
      '共 ' + sessionItems.length + ' 场签到活动';
  };
  const historyTools = document.querySelector('[data-history-tools]');
  if (historyTools) {
    historyTools.hidden = false;
    search.addEventListener('input', filterSessions);
    filterButtons.forEach((button) => button.addEventListener('click', () => {
      activeFilter = button.dataset.sessionFilter;
      filterButtons.forEach((tab) => {
        const selected = tab === button;
        tab.classList.toggle('is-selected', selected);
        tab.setAttribute('aria-pressed', String(selected));
      });
      filterSessions();
    }));
  }

  const recordSearch = document.querySelector('[data-record-search]');
  if (recordSearch) {
    document.querySelector('[data-record-tools]').hidden = false;
    const rows = Array.from(document.querySelectorAll('[data-record-row]'));
    recordSearch.addEventListener('input', () => {
      const query = normalizeSearch(recordSearch.value);
      let visible = 0;
      rows.forEach((row) => {
        row.hidden = !normalizeSearch(row.dataset.searchable).includes(query);
        if (!row.hidden) visible++;
      });
      document.querySelector('[data-record-match]').textContent =
        query ? '找到 ' + visible + ' 位同学' : '共 ' + rows.length + ' 位同学';
      document.querySelector('[data-record-empty]').hidden = visible !== 0;
      document.querySelector('.table-wrap').hidden = visible === 0;
    });
  }

  const dateLabel = document.querySelector('[data-today]');
  const updateDate = () => {
    if (dateLabel) dateLabel.textContent = new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', weekday: 'long',
    }).format(new Date());
  };
  updateDate();

  const timedElements = document.querySelectorAll('[data-session-end]');
  const tickSessions = () => {
    const now = Date.now() / 1000;
    let changed = false;
    timedElements.forEach((element) => {
      const remaining = Math.max(0, Math.ceil(Number(element.dataset.sessionEnd) - now));
      const open = element.dataset.closed !== '1' && remaining > 0;
      const state = open ? 'active' : 'ended';
      if (element.dataset.sessionState !== state) {
        element.dataset.sessionState = state;
        const badge = element.matches('[data-session-status]') ? element : element.querySelector('[data-session-status]');
        if (badge) {
          badge.classList.toggle('badge-active', open);
          badge.classList.toggle('badge-ended', !open);
          badge.querySelector('[data-status-label]').textContent = open ? '进行中' : '已结束';
        }
        const sessionIcon = element.querySelector('.session-icon');
        if (sessionIcon) sessionIcon.classList.toggle('session-icon-active', open);
        changed = true;
      }
      if (!element.hasAttribute('data-session-panel')) return;
      const wasOpen = !element.classList.contains('code-card-ended');
      element.classList.toggle('code-card-ended', !open);
      const countdown = element.querySelector('[data-countdown]');
      countdown.textContent = open ?
        String(Math.floor(remaining / 60)).padStart(2, '0') + ':' + String(remaining % 60).padStart(2, '0') : '已结束';
      const total = Math.max(1, Number(element.dataset.sessionEnd) - Number(element.dataset.sessionStart));
      element.querySelector('[data-time-progress]').style.setProperty('--time-progress', String(open ? Math.min(1, remaining / total) : 0));
      if (!open && wasOpen) {
        element.querySelector('[data-code-title]').textContent = '本次签到已结束。';
        element.querySelector('[data-code-caption]').textContent = '签到码已失效，记录已保留。';
        element.querySelector('[data-countdown-label]').textContent = '签到状态';
        element.querySelectorAll('[data-open-only]').forEach((control) => { control.hidden = true; });
        const empty = document.querySelector('.records-empty');
        if (empty) {
          empty.querySelector('h3').textContent = '本次暂无签到记录';
          empty.querySelector('p').textContent = '本次签到结束前，没有同学提交签到。';
        }
        if (pendingForm && pendingForm.closest('[data-session-panel]') === element) {
          pendingForm = null;
          if (dialog.open) dialog.close();
        }
        announce('本次签到已到期，签到码已失效。');
      }
    });
    const activeCount = document.querySelector('[data-active-count]');
    if (activeCount) activeCount.textContent = sessionItems.filter((item) => item.dataset.sessionState === 'active').length;
    if (changed && sessionItems.length) filterSessions();
  };
  if (timedElements.length) {
    tickSessions();
    window.setInterval(() => { if (!document.hidden) tickSessions(); }, 1000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) tickSessions(); });
  }
  window.addEventListener('pageshow', () => { tickSessions(); updateDate(); });
})();
