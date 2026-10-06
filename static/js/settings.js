(() => {
  'use strict';
  const state = window.dashboardSettings;
  const feedback = document.getElementById('settings-feedback');
  function notify(message, error = false) {
    feedback.textContent = message; feedback.dataset.error = String(error); feedback.hidden = false;
  }
  document.querySelectorAll('[data-preference]').forEach(button => {
    button.addEventListener('click', async () => {
      const key = button.dataset.preference, value = !state.preferences[key];
      button.disabled = true;
      try {
        if (key === 'site_sound' && value) window.primeDashboardAudio();
        if (key === 'site_desktop' && value) {
          if (!('Notification' in window)) throw new Error('Desktop notifications are not supported by this browser.');
          const permission = await Notification.requestPermission();
          if (permission !== 'granted') throw new Error('Desktop notifications were not enabled. Allow notifications in your browser settings, then try again.');
        }
        const data = await window.settingsRequest('/api/settings/preferences', 'PATCH', {[key]: value});
        window.applyDashboardPreferences({...state.preferences, [key]: data.preferences[key]});
        button.setAttribute('aria-checked', String(data.preferences[key]));
        notify(key.startsWith('email_') ? 'Preference saved. Email delivery is not active yet.' : 'Preference saved.');
      } catch (e) { notify(e.message, true); }
      finally { button.disabled = false; }
    });
  });
  const themeOptions = document.getElementById('theme-options');
  themeOptions.addEventListener('change', async event => {
    if (event.target.name !== 'theme') return;
    themeOptions.disabled = true;
    try {
      const data = await window.settingsRequest('/api/settings/preferences', 'PATCH', {theme: event.target.value});
      window.applyDashboardPreferences({...state.preferences, theme: data.preferences.theme});
      notify('Appearance saved.');
    } catch (e) {
      themeOptions.querySelector(`[value="${state.preferences.theme}"]`).checked = true;
      notify(e.message, true);
    } finally { themeOptions.disabled = false; }
  });

  const dialog = document.getElementById('profile-dialog'), form = document.getElementById('profile-form');
  const error = document.getElementById('profile-error'), save = document.getElementById('profile-save');
  const cancel = document.getElementById('profile-cancel'), valueInput = document.getElementById('profile-value');
  const address = document.getElementById('profile-address'), current = document.getElementById('profile-current');
  const newPassword = document.getElementById('profile-new'), confirmation = document.getElementById('profile-confirm');
  let field, opener, saving = false;
  const labels = {full_name: 'display name', email: 'email', password: 'password', work_address: 'work address'};
  function group(id, visible) {
    const el = document.getElementById(id); el.hidden = !visible;
    el.querySelectorAll('input,textarea').forEach(input => { input.disabled = !visible; input.required = visible && input !== address; });
  }
  document.querySelectorAll('[data-change-field]').forEach(button => button.addEventListener('click', () => {
    opener = button; field = button.dataset.changeField; form.reset(); error.hidden = true;
    document.getElementById('profile-dialog-title').textContent = `Change ${labels[field]}`;
    document.getElementById('profile-value-label').textContent = field === 'email' ? 'Email' : 'Display name';
    document.getElementById('profile-dialog-help').textContent = field === 'password'
      ? 'Use 8–128 characters. Other sessions will be signed out after saving.'
      : field === 'email' ? 'This is your sign-in email. Enter your current password to confirm the change.' : 'Update your details, then save. Cancel leaves them unchanged.';
    group('profile-value-group', ['full_name', 'email'].includes(field));
    group('profile-address-group', field === 'work_address');
    group('profile-current-group', ['email', 'password'].includes(field));
    group('profile-password-group', field === 'password');
    valueInput.type = field === 'email' ? 'email' : 'text'; valueInput.maxLength = field === 'email' ? 320 : 200;
    valueInput.autocomplete = field === 'email' ? 'email' : 'name';
    valueInput.value = state.profile[field] || ''; address.value = state.profile.work_address || '';
    dialog.showModal();
    (field === 'password' ? current : field === 'work_address' ? address : valueInput).focus();
  }));
  cancel.addEventListener('click', () => dialog.close());
  dialog.addEventListener('cancel', event => { if (saving) event.preventDefault(); });
  dialog.addEventListener('close', () => { form.reset(); opener?.focus(); });
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (saving) return;
    if (field === 'password' && newPassword.value !== confirmation.value) {
      error.textContent = 'New passwords do not match.'; error.hidden = false; confirmation.focus(); return;
    }
    const body = field === 'password'
      ? {current_password: current.value, new_password: newPassword.value, confirm_password: confirmation.value}
      : {field, value: field === 'work_address' ? address.value : valueInput.value, ...(field === 'email' ? {current_password: current.value} : {})};
    saving = true; save.disabled = cancel.disabled = true; save.textContent = 'Saving…'; error.hidden = true;
    const activeInputs = [...form.querySelectorAll('input,textarea')].filter(input => !input.disabled);
    activeInputs.forEach(input => { input.readOnly = true; });
    try {
      const data = await window.settingsRequest(`/api/settings/${field === 'password' ? 'password' : 'profile'}`, field === 'password' ? 'POST' : 'PATCH', body);
      if (data.profile) {
        state.profile = data.profile;
        document.querySelectorAll('[data-profile-value]').forEach(el => {
          const key = el.dataset.profileValue;
          if (key !== 'password') el.textContent = state.profile[key] || 'Not set';
        });
        window.dispatchEvent(new CustomEvent('dashboard-profile-changed'));
      }
      dialog.close(); notify(data.message);
    } catch (e) { error.textContent = e.message; error.hidden = false; }
    finally { saving = false; save.disabled = cancel.disabled = false; save.textContent = 'Save'; activeInputs.forEach(input => { input.readOnly = false; }); }
  });
})();
