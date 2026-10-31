(function () {
  // Tools that went unused through the 2026 season. They stay installed and
  // reachable by URL; Settings > Retired Tools brings them back on a machine.
  const RETIRED_STORAGE_KEY = 'csrn.showRetiredTools.v1';
  const RETIRED_STYLE_ID = 'csrn-retired-tools-style';

  function showRetired() {
    try {
      return localStorage.getItem(RETIRED_STORAGE_KEY) === '1';
    } catch (error) {
      return false;
    }
  }

  function applyRetired(show) {
    document.documentElement.classList.toggle('show-retired', show);
  }

  function setShowRetired(show) {
    try {
      if (show) localStorage.setItem(RETIRED_STORAGE_KEY, '1');
      else localStorage.removeItem(RETIRED_STORAGE_KEY);
    } catch (error) {
      // The switch still applies to this page.
    }
    applyRetired(Boolean(show));
  }

  if (!document.getElementById(RETIRED_STYLE_ID)) {
    const style = document.createElement('style');
    style.id = RETIRED_STYLE_ID;
    style.textContent = 'html:not(.show-retired) .retired-tool { display: none !important; }';
    document.head.appendChild(style);
  }
  applyRetired(showRetired());

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
      ['themes', 'Theme Manager', '/themes', true],
      ['assets', 'Assets'],
      ['sponsors', 'Sponsors'],
      ['packages', 'Broadcast Packages', null, true],
    ]],
    ['Publishing', [
      ['social', 'Social Publishing', '/social'],
      ['recaps', 'Game Recaps', '/recaps', true],
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

      items.forEach(([key, text, explicitUrl, retired]) => {
        const link = document.createElement('a');
        if (retired) link.classList.add('retired-tool');
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
    showRetired,
    setShowRetired,
  };
}());
