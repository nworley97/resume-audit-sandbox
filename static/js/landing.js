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
    const tabs = Array.from(tabContainer.querySelectorAll('[role="tab"]'));
    const panels = panelContainer.querySelectorAll('[role="tabpanel"]');

    // Default: activate first tab
    if (tabs.length > 0) {
      tabs[0].classList.add('active');
    }

    function activateTab(tab) {
      var target = tab.dataset.tab;

      // Update ARIA and visual state on all tabs
      tabs.forEach(function (t) {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
        t.setAttribute('tabindex', '-1');
      });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      tab.setAttribute('tabindex', '0');
      tab.focus();

      // Show matching panel, hide others
      panels.forEach(function (p) {
        if (p.dataset.panel === target) {
          p.classList.remove('hidden');
        } else {
          p.classList.add('hidden');
        }
      });
    }

    // Click handler
    tabContainer.addEventListener('click', function (e) {
      var pill = e.target.closest('[role="tab"]');
      if (!pill) return;
      activateTab(pill);
    });

    // Keyboard navigation
    tabContainer.addEventListener('keydown', function (e) {
      var currentTab = e.target.closest('[role="tab"]');
      if (!currentTab) return;

      var index = tabs.indexOf(currentTab);
      var newIndex;

      if (e.key === 'ArrowRight') {
        newIndex = (index + 1) % tabs.length;
      } else if (e.key === 'ArrowLeft') {
        newIndex = (index - 1 + tabs.length) % tabs.length;
      } else if (e.key === 'Home') {
        newIndex = 0;
      } else if (e.key === 'End') {
        newIndex = tabs.length - 1;
      } else {
        return;
      }

      e.preventDefault();
      activateTab(tabs[newIndex]);
    });
  }

  // ── Accordion (Apply for Jobs section) with cycling images ─────
  const accordion = document.getElementById('apply-accordion');
  const applyImages = document.getElementById('apply-images');
  if (accordion) {
    const items = accordion.querySelectorAll('.accordion-item');
    const stepImgs = applyImages ? applyImages.querySelectorAll('.apply-step-img') : [];
    const stepIcons = applyImages ? applyImages.querySelectorAll('[data-step-icon]') : [];

    function updateApplyStep(stepIndex) {
      // Swap images
      stepImgs.forEach(function (img) {
        if (img.dataset.stepImg === String(stepIndex)) {
          img.classList.remove('hidden');
        } else {
          img.classList.add('hidden');
        }
      });
      // Highlight active icon
      stepIcons.forEach(function (icon) {
        if (icon.dataset.stepIcon === String(stepIndex)) {
          icon.classList.remove('text-gray-400');
          icon.classList.add('text-landing-blue');
        } else {
          icon.classList.remove('text-landing-blue');
          icon.classList.add('text-gray-400');
        }
      });
    }

    accordion.addEventListener('click', function (e) {
      const trigger = e.target.closest('.accordion-trigger');
      if (!trigger) return;

      const item = trigger.closest('.accordion-item');
      const wasOpen = item.classList.contains('open');

      // Close all
      items.forEach(function (i) { i.classList.remove('open'); });

      // Toggle clicked (if it was closed, open it)
      if (!wasOpen) {
        item.classList.add('open');
        var step = item.dataset.step;
        if (step !== undefined) {
          updateApplyStep(parseInt(step, 10));
        }
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

    function setMobileMenuState(open) {
      isOpen = open;
      menuBtn.setAttribute('aria-expanded', String(open));
      mobileMenu.setAttribute('aria-hidden', String(!open));
      if (open) {
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
    }

    menuBtn.addEventListener('click', function () {
      setMobileMenuState(!isOpen);
    });

    // Close menu on link click
    mobileMenu.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        setMobileMenuState(false);
      });
    });
  }

  // ── Pricing Toggle (Monthly / Yearly) ────────────────────────
  var monthlyBtn = document.getElementById('pricing-monthly-btn');
  var yearlyBtn = document.getElementById('pricing-yearly-btn');
  var currentPricingCycle = 'monthly';
  if (monthlyBtn && yearlyBtn) {
    var priceEls = document.querySelectorAll('.pricing-amount');

    function setPricingCycle(cycle) {
      currentPricingCycle = cycle;
      // Toggle button styles
      if (cycle === 'monthly') {
        monthlyBtn.classList.add('bg-landing-blue', 'text-white');
        monthlyBtn.classList.remove('bg-white', 'text-black', 'border', 'border-landing-blue');
        yearlyBtn.classList.remove('bg-landing-blue', 'text-white');
        yearlyBtn.classList.add('bg-white', 'text-black', 'border', 'border-landing-blue');
      } else {
        yearlyBtn.classList.add('bg-landing-blue', 'text-white');
        yearlyBtn.classList.remove('bg-white', 'text-black', 'border', 'border-landing-blue');
        monthlyBtn.classList.remove('bg-landing-blue', 'text-white');
        monthlyBtn.classList.add('bg-white', 'text-black', 'border', 'border-landing-blue');
      }
      // Swap price text
      priceEls.forEach(function (el) {
        el.textContent = cycle === 'monthly' ? el.dataset.monthly : el.dataset.yearly;
      });
    }

    monthlyBtn.addEventListener('click', function () { setPricingCycle('monthly'); });
    yearlyBtn.addEventListener('click', function () { setPricingCycle('yearly'); });
  }

  // ── Landing Signup Modal ────────────────────────────────────
  var signupModal = document.getElementById('landing-signup-modal');
  var signupClose = document.getElementById('landing-signup-close');
  var signupBtns = document.querySelectorAll('.landing-signup-btn');
  if (signupModal && signupBtns.length) {
    signupBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var plan = btn.dataset.plan;
        var planName = btn.dataset.planName;
        var price = currentPricingCycle === 'monthly' ? btn.dataset.monthlyPrice : btn.dataset.yearlyPrice;
        document.getElementById('landing-form-plan').value = plan;
        document.getElementById('landing-form-cycle').value = currentPricingCycle;
        document.getElementById('landing-display-plan').textContent = planName;
        document.getElementById('landing-display-price').textContent = price;
        signupModal.classList.remove('hidden');
        signupModal.classList.add('flex');
      });
    });
    if (signupClose) {
      signupClose.addEventListener('click', function () {
        signupModal.classList.add('hidden');
        signupModal.classList.remove('flex');
      });
    }
    signupModal.addEventListener('click', function (e) {
      if (e.target === signupModal) {
        signupModal.classList.add('hidden');
        signupModal.classList.remove('flex');
      }
    });
  }

  // ── FAQ Accordion ─────────────────────────────────────────────
  const faqAccordion = document.getElementById('faq-accordion');
  if (faqAccordion) {
    const faqItems = faqAccordion.querySelectorAll('.faq-item');

    faqAccordion.addEventListener('click', function (e) {
      const trigger = e.target.closest('.faq-trigger');
      if (!trigger) return;

      const item = trigger.closest('.faq-item');
      const answer = item.querySelector('.faq-answer');
      const icon = item.querySelector('.faq-icon');
      const wasOpen = !answer.classList.contains('hidden');

      // Close all FAQ items
      faqItems.forEach(function (fi) {
        fi.querySelector('.faq-answer').classList.add('hidden');
        fi.querySelector('.faq-icon').textContent = 'add';
      });

      // Toggle clicked (if it was closed, open it)
      if (!wasOpen) {
        answer.classList.remove('hidden');
        icon.textContent = 'close';
      }
    });
  }

  // ── Demo Video Modal ──────────────────────────────────────────
  var demoPlayBtn = document.getElementById('demo-play-btn');
  var demoModal = document.getElementById('demo-modal');
  var demoModalClose = document.getElementById('demo-modal-close');
  var demoVideo = document.getElementById('demo-video');

  if (demoPlayBtn && demoModal) {
    demoPlayBtn.addEventListener('click', function () {
      demoModal.classList.remove('hidden');
      demoModal.classList.add('flex');
      document.body.style.overflow = 'hidden';
      if (demoVideo) demoVideo.play();
    });

    function closeDemoModal() {
      if (demoVideo) { demoVideo.pause(); }
      demoModal.classList.add('hidden');
      demoModal.classList.remove('flex');
      document.body.style.overflow = '';
    }

    if (demoModalClose) {
      demoModalClose.addEventListener('click', closeDemoModal);
    }

    demoModal.addEventListener('click', function (e) {
      if (e.target === demoModal) {
        closeDemoModal();
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !demoModal.classList.contains('hidden')) {
        closeDemoModal();
      }
    });
  }

  // ── Smooth scroll for anchor links ─────────────────────────────
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        const offset = 64; // navbar height
        const top = target.getBoundingClientRect().top + window.pageYOffset - offset;
        window.scrollTo({ top: top, behavior: 'smooth' });
      }
    });
  });
})();
