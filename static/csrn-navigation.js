(function () {
  const groups = [
    ['Game Day', [
      ['pregame', 'Pre-Game Setup'],
      ['command', 'Command Center'],
      ['statistician', 'Statistician'],
      ['statistics', 'Statistics'],
      ['obs', 'OBS Manager'],
    ]],
    ['Setup', [
      ['games', 'Game Manager'],
      ['schools', 'School Database'],
      ['rosters', 'Rosters'],
      ['broadcasters', 'Personnel'],
    ]],
    ['Production', [
      ['graphics', 'Graphics'],

      ['themes', 'Theme Manager', '/themes'],
      ['assets', 'Assets'],
      ['sponsors', 'Sponsors'],
      ['packages', 'Broadcast Packages'],
    ]],
    ['Publishing', [
      ['social', 'Social Publishing', '/social'],
      ['recaps', 'Game Recaps', '/recaps'],
    ]],
    ['System', [
      ['settings', 'Settings'],
      ['diagnostics', 'Release Readiness'],
    ]],
  ];

  let active = '';

  function mainUrl(key) {
    return `/?module=${encodeURIComponent(key)}`;
  }

  function activate(key) {
    active = key;
    document.querySelectorAll('[data-csrn-key]').forEach((element) => {
      element.classList.toggle('nav-active', element.dataset.csrnKey === key);
    });
    document.querySelectorAll('.csrn-nav-group').forEach((group) => {
      group.classList.toggle('active', Boolean(group.querySelector('.nav-active')));
    });
  }

  function closeMenus(except = null) {
    document.querySelectorAll('.csrn-nav-group[open]').forEach((details) => {
      if (details !== except) details.removeAttribute('open');
    });
  }

  function closeMobileNav(nav) {
    nav.classList.remove('open');
    const toggle = nav.querySelector('.csrn-nav-toggle');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
  }

  function closeNavigation(nav) {
    closeMenus();
    closeMobileNav(nav);
  }

  function mount(nav) {
    active = nav.dataset.active || 'command';
    nav.classList.add('csrn-nav');
    nav.innerHTML = [
      '<button type="button" class="csrn-nav-toggle" aria-expanded="false">',
      '<span>Menu</span><span>☰</span>',
      '</button>',
      '<div class="csrn-nav-groups"></div>',
    ].join('');

    const wrap = nav.querySelector('.csrn-nav-groups');

    groups.forEach(([label, items]) => {
      const details = document.createElement('details');
      details.className = 'csrn-nav-group';

      const summary = document.createElement('summary');
      summary.textContent = label;
      details.appendChild(summary);

      const menu = document.createElement('div');
      menu.className = 'csrn-nav-menu';

      items.forEach(([key, text, explicitUrl]) => {
        const link = document.createElement('a');
        link.href = explicitUrl || mainUrl(key);
        link.dataset.csrnKey = key;
        link.textContent = text;

        link.addEventListener('click', (event) => {
          const canSwitchLocally = !explicitUrl && typeof window.showModule === 'function';
          if (canSwitchLocally) {
            event.preventDefault();
            window.showModule(key);
            history.replaceState(null, '', mainUrl(key));
            activate(key);
          }
          closeNavigation(nav);
        });

        menu.appendChild(link);
      });

      details.appendChild(menu);
      details.addEventListener('toggle', () => {
        if (details.open) closeMenus(details);
      });
      wrap.appendChild(details);
    });

    const toggle = nav.querySelector('.csrn-nav-toggle');
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
      if (!open) closeMenus();
    });

    document.addEventListener('click', (event) => {
      if (!nav.contains(event.target)) closeNavigation(nav);
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeNavigation(nav);
    });

    activate(active);
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-csrn-navigation]').forEach(mount);
  });

  window.CSRNNavigation = {
    setActive: activate,
    close: closeMenus,
  };
}());
