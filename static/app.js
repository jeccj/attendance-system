// 只做交互增强；关闭 JavaScript 后仍可完成登录、签到和导出。
document.querySelectorAll('form').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
      event.preventDefault();
      return;
    }
    const button = form.querySelector('[data-submit-text]');
    if (button) {
      button.disabled = true;
      button.textContent = button.dataset.submitText;
    }
  });
});

document.querySelectorAll('[data-copy]').forEach((button) => {
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      const original = button.textContent;
      button.textContent = '已复制';
      window.setTimeout(() => { button.textContent = original; }, 2000);
    } catch {
      window.prompt('请复制签到码：', button.dataset.copy);
    }
  });
});

// 浏览器后退可能恢复已禁用的按钮。
window.addEventListener('pageshow', () => {
  document.querySelectorAll('[data-submit-text]').forEach((button) => {
    if (!button.dataset.originalText) button.dataset.originalText = button.textContent;
    button.disabled = false;
    button.textContent = button.dataset.originalText;
  });
});
