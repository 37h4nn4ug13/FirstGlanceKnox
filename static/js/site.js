(() => {
  'use strict';
  const menu = document.querySelector('.menu-toggle');
  const navigation = document.getElementById('primary-navigation');
  if (menu && navigation) {
    const closeMenu = () => { menu.setAttribute('aria-expanded', 'false'); navigation.classList.remove('is-open'); };
    menu.addEventListener('click', () => {
      const open = menu.getAttribute('aria-expanded') !== 'true';
      menu.setAttribute('aria-expanded', String(open)); navigation.classList.toggle('is-open', open);
    });
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && navigation.classList.contains('is-open')) { closeMenu(); menu.focus(); } });
    document.addEventListener('click', event => { if (!navigation.contains(event.target) && !menu.contains(event.target)) closeMenu(); });
    window.matchMedia('(min-width: 761px)').addEventListener('change', closeMenu);
  }
  const errorSummary = document.querySelector('.error-summary');
  if (errorSummary) errorSummary.focus();
  const dialog = document.getElementById('gallery-lightbox');
  const links = [...document.querySelectorAll('[data-lightbox]')];
  if (dialog && typeof dialog.showModal === 'function' && links.length) {
    let active = 0;
    let opener;
    const img = document.getElementById('lightbox-image');
    const caption = document.getElementById('lightbox-caption');
    const count = document.getElementById('lightbox-count');
    const show = index => {
      active = (index + links.length) % links.length;
      const link = links[active]; img.src = link.href; img.alt = link.dataset.alt || '';
      caption.textContent = link.dataset.caption || ''; count.textContent = `${active + 1} of ${links.length}`;
    };
    links.forEach((link, index) => link.addEventListener('click', event => {
      event.preventDefault(); opener = link; show(index); dialog.showModal();
    }));
    dialog.querySelector('.lightbox-close').addEventListener('click', () => dialog.close());
    dialog.querySelector('[data-lightbox-prev]').addEventListener('click', () => show(active - 1));
    dialog.querySelector('[data-lightbox-next]').addEventListener('click', () => show(active + 1));
    dialog.addEventListener('keydown', event => {
      if (event.key === 'ArrowRight') { event.preventDefault(); show(active + 1); }
      if (event.key === 'ArrowLeft') { event.preventDefault(); show(active - 1); }
    });
    dialog.addEventListener('close', () => { img.removeAttribute('src'); if (opener) opener.focus(); });
    dialog.addEventListener('click', event => {
      if (event.target === dialog) { const rect = dialog.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close(); }
    });
    if (links.length < 2) dialog.querySelector('.lightbox-controls').hidden = true;
  }
})();
