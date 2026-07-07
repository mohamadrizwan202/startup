// Modern navbar toggle (PureFyul)
(function initNavbar() {
  'use strict';

  const header = document.querySelector('.pf-header');
  const toggleBtn = document.querySelector('.pf-nav__toggle');
  const menu = document.getElementById('pf-nav-menu');

  if (!header || !toggleBtn || !menu) return;

  function setOpen(open) {
    header.classList.toggle('is-open', open);
    toggleBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  // Toggle on button click
  toggleBtn.addEventListener('click', (e) => {
    e.preventDefault();
    const isOpen = header.classList.contains('is-open');
    setOpen(!isOpen);
  });

  // Close when clicking a link inside menu (mobile)
  menu.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link) return;
    setOpen(false);
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (header.contains(e.target)) return;
    setOpen(false);
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') setOpen(false);
  });
})();
