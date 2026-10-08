// 在加载样式前恢复主题，避免手动选择夜晚模式后刷新时闪白。
(() => {
  'use strict';

  const storageKey = 'attendance-theme';
  const root = document.documentElement;
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
  const validTheme = (value) => value === 'light' || value === 'dark' ? value : null;
  const readPreference = () => {
    try { return validTheme(window.localStorage.getItem(storageKey)); }
    catch { return null; }
  };
  let preference = readPreference();

  const applyTheme = () => {
    const theme = preference || (systemTheme.matches ? 'dark' : 'light');
    const dark = theme === 'dark';
    root.dataset.theme = theme;
    document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
      meta.content = dark ? '#161618' : '#f5f5f7';
    });
    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
      button.setAttribute('aria-checked', String(dark));
      button.title = dark ? '切换到白天模式' : '切换到夜晚模式';
    });
  };

  applyTheme();
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
      button.hidden = false;
      button.addEventListener('click', () => {
        preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
        try { window.localStorage.setItem(storageKey, preference); }
        catch { /* 禁止本地存储时，当前页面仍可切换主题。 */ }
        applyTheme();
      });
    });
    applyTheme();
  });

  const followSystem = () => { if (!preference) applyTheme(); };
  if (systemTheme.addEventListener) systemTheme.addEventListener('change', followSystem);
  else systemTheme.addListener(followSystem);

  // 同步其他标签页的选择，以及浏览器后退恢复的页面。
  window.addEventListener('storage', (event) => {
    if (event.key === storageKey || event.key === null) {
      preference = validTheme(event.newValue);
      applyTheme();
    }
  });
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) preference = readPreference();
    applyTheme();
  });
})();
