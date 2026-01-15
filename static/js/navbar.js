// Navbar mobile menu: close on outside click, link click, and Escape key
(function initNavbarMenu() {
  'use strict';
  
  const navCheck = document.getElementById('pf-nav-check');
  const navCollapse = document.querySelector('.pf-nav-collapse');
  const navbar = document.querySelector('.pf-navbar');
  
  if (!navCheck || !navCollapse || !navbar) {
    // Navbar elements not found, skip initialization
    return;
  }

  // Close menu when clicking outside
  document.addEventListener('click', (e) => {
    // Don't close if clicking inside navbar (including collapse and hamburger)
    if (navbar.contains(e.target)) {
      return;
    }
    
    // Close menu if it's open
    if (navCheck.checked) {
      navCheck.checked = false;
    }
  });

  // Close menu when clicking a link inside the dropdown
  const navLinks = navCollapse.querySelectorAll('a');
  navLinks.forEach(link => {
    link.addEventListener('click', () => {
      if (navCheck.checked) {
        navCheck.checked = false;
      }
    });
  });

  // Close menu on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && navCheck.checked) {
      navCheck.checked = false;
    }
  });
})();
