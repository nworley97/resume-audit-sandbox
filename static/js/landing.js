/**
 * AlteraSF Landing Page — Interactions
 * Handles: scroll reveals, navbar scroll state, tabs, accordion, mobile menu, smooth scroll
 */

(function () {
  'use strict';

  // ── Scroll Reveal ──────────────────────────────────────────────
  const revealElements = document.querySelectorAll('.reveal');
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          revealObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
  );
  revealElements.forEach((el) => revealObserver.observe(el));

  // ── Navbar scroll shadow ───────────────────────────────────────
  const nav = document.getElementById('landing-nav');
  if (nav) {
    let ticking = false;
    window.addEventListener('scroll', function () {
      if (!ticking) {
        requestAnimationFrame(function () {
          nav.classList.toggle('navbar-scrolled', window.scrollY > 10);
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  // ── Tab switching (Tools section) ──────────────────────────────
  const tabContainer = document.getElementById('tools-tabs');
  const panelContainer = document.getElementById('tools-panels');
  if (tabContainer && panelContainer) {
    const tabs = tabContainer.querySelectorAll('.tab-pill');
    const panels = panelContainer.querySelectorAll('.tab-panel');

    tabContainer.addEventListener('click', function (e) {
      const pill = e.target.closest('.tab-pill');
      if (!pill) return;

      const target = pill.dataset.tab;

      // Update active tab
      tabs.forEach((t) => t.classList.remove('active'));
      pill.classList.add('active');

      // Show matching panel
      panels.forEach((p) => {
        if (p.dataset.panel === target) {
          p.classList.remove('hidden');
        } else {
          p.classList.add('hidden');
        }
      });
    });
  }

  // ── Accordion (Apply for Jobs section) ─────────────────────────
  const accordion = document.getElementById('apply-accordion');
  if (accordion) {
    const items = accordion.querySelectorAll('.accordion-item');

    accordion.addEventListener('click', function (e) {
      const trigger = e.target.closest('.accordion-trigger');
      if (!trigger) return;

      const item = trigger.closest('.accordion-item');
      const wasOpen = item.classList.contains('open');

      // Close all
      items.forEach((i) => i.classList.remove('open'));

      // Toggle clicked (if it was closed, open it)
      if (!wasOpen) {
        item.classList.add('open');
      }
    });
  }

  // ── Mobile menu ────────────────────────────────────────────────
  const menuBtn = document.getElementById('mobile-menu-btn');
  const mobileMenu = document.getElementById('mobile-menu');
  if (menuBtn && mobileMenu) {
    let isOpen = false;
    const burgerTop = document.getElementById('burger-top');
    const burgerMid = document.getElementById('burger-mid');
    const burgerBot = document.getElementById('burger-bot');

    menuBtn.addEventListener('click', function () {
      isOpen = !isOpen;
      if (isOpen) {
        mobileMenu.style.maxHeight = mobileMenu.scrollHeight + 'px';
        burgerTop.style.transform = 'rotate(45deg) translateY(5px)';
        burgerMid.style.opacity = '0';
        burgerBot.style.transform = 'rotate(-45deg) translateY(-5px)';
      } else {
        mobileMenu.style.maxHeight = '0';
        burgerTop.style.transform = '';
        burgerMid.style.opacity = '';
        burgerBot.style.transform = '';
      }
    });

    // Close menu on link click
    mobileMenu.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        isOpen = false;
        mobileMenu.style.maxHeight = '0';
        burgerTop.style.transform = '';
        burgerMid.style.opacity = '';
        burgerBot.style.transform = '';
      });
    });
  }

  // ── Smooth scroll for anchor links ─────────────────────────────
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        const offset = 80; // navbar height + padding
        const top = target.getBoundingClientRect().top + window.pageYOffset - offset;
        window.scrollTo({ top: top, behavior: 'smooth' });
      }
    });
  });
})();
