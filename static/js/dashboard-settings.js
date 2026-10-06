/* Shared, account-backed website preferences. No browser storage of credentials. */
(() => {
  'use strict';
  const state = window.dashboardSettings;
  window.settingsRequest = async (path, method, body) => {
    const response = await fetch(path, {
      method, credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf_token},
      body: JSON.stringify(body)
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || (response.status === 401 ? 'Please sign in again.' : 'Could not save. Please try again.'));
    return data;
  };
  window.applyDashboardPreferences = preferences => {
    state.preferences = preferences;
    document.documentElement.dataset.theme = preferences.theme;
    document.documentElement.classList.toggle('dark', preferences.theme === 'dark');
    window.dispatchEvent(new CustomEvent('dashboard-preferences-changed'));
  };
  let audio;
  // Browsers require a user gesture before audio can play.
  window.primeDashboardAudio = () => {
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (Audio) { audio ||= new Audio(); audio.resume().catch(() => {}); }
  };
  const primeEnabledAudio = () => { if (state.preferences.site_sound) window.primeDashboardAudio(); };
  document.addEventListener('pointerdown', primeEnabledAudio);
  document.addEventListener('keydown', primeEnabledAudio);
  window.announceDashboardNotification = notification => {
    if (!state.preferences.site_alerts) return;
    if (state.preferences.site_sound && audio?.state === 'running') {
      const tone = audio.createOscillator(), gain = audio.createGain();
      tone.connect(gain); gain.connect(audio.destination);
      tone.frequency.value = 660;
      gain.gain.setValueAtTime(0.07, audio.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.18);
      tone.start(); tone.stop(audio.currentTime + 0.2);
    }
    if (state.preferences.site_desktop && 'Notification' in window && Notification.permission === 'granted' && document.hidden) {
      // Avoid exposing applicant names or other private details on a lock screen.
      try { new Notification('AlteraSF', {body: 'You have a new dashboard notification.', tag: 'altera-dashboard'}); } catch (_) {}
    }
  };
})();
