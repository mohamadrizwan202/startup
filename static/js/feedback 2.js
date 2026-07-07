// Feedback Widget JavaScript
(function() {
  'use strict';

  if (window.__pfFeedbackInit) return;
  window.__pfFeedbackInit = true;

  const FEEDBACK_API_URL = '/api/feedback';
  const MAX_MESSAGE_LENGTH = 1500;
  const MIN_MESSAGE_LENGTH = 5;

  // DOM Elements
  const widget = document.getElementById('pf-feedback-widget');
  const btn = document.getElementById('pf-feedback-btn');
  const panel = document.getElementById('pf-feedback-panel');
  const backdrop = document.getElementById('pf-feedback-backdrop');
  const closeBtn = document.getElementById('pf-feedback-close');
  const form = document.getElementById('pf-feedback-form');
  const messageEl = document.getElementById('pf-feedback-message');
  const messageTextarea = document.getElementById('pf-feedback-message-text');
  const charCountEl = document.getElementById('pf-feedback-char-count');
  const submitBtn = document.getElementById('pf-feedback-submit');
  const submitText = submitBtn.querySelector('.pf-feedback-submit-text');
  const submitSpinner = submitBtn.querySelector('.pf-feedback-submit-spinner');

  let pfBtnHoldTimer = null;
  let pfCloseTimer = null;
  const PF_BTN_HOLD_MS = 220;

  // Get current page URL
  function getCurrentPage() {
    return window.location.pathname || '/';
  }

  // Show/hide panel
  function togglePanel() {
    const isHidden = panel.getAttribute('aria-hidden') === 'true';
    panel.setAttribute('aria-hidden', !isHidden);
    btn.setAttribute('aria-expanded', isHidden);

    if (isHidden) {
      if (pfCloseTimer) { clearTimeout(pfCloseTimer); pfCloseTimer = null; }
      if (pfBtnHoldTimer) { clearTimeout(pfBtnHoldTimer); pfBtnHoldTimer = null; }
      widget?.classList.remove('is-closing');
      btn?.classList.remove('pf-feedback-btn-hold');
      widget?.classList.add('is-open');
      backdrop?.classList.add('is-open');
      backdrop?.setAttribute('aria-hidden', 'false');
      // Focus on first input when opening
      setTimeout(() => {
        const firstInput = form.querySelector('input, textarea, select');
        if (firstInput) firstInput.focus();
      }, 100);
    } else {
      closePanel();
    }
  }

  // Close panel — is-closing allows click-through; delay widget is-open removal to avoid flash
  function closePanel() {
    widget?.classList.add('is-closing');
    panel?.setAttribute('aria-hidden', 'true');
    btn?.setAttribute('aria-expanded', 'false');
    backdrop?.classList.remove('is-open');
    backdrop?.setAttribute('aria-hidden', 'true');
    if (pfCloseTimer) clearTimeout(pfCloseTimer);
    pfCloseTimer = setTimeout(() => {
      widget?.classList.remove('is-open');
      widget?.classList.remove('is-closing');
      pfCloseTimer = null;
    }, 220);
    // prevent 1-frame shadow flash on close
    btn?.classList.add('pf-feedback-btn-hold');
    if (pfBtnHoldTimer) clearTimeout(pfBtnHoldTimer);
    pfBtnHoldTimer = setTimeout(() => {
      btn?.classList.remove('pf-feedback-btn-hold');
      pfBtnHoldTimer = null;
    }, PF_BTN_HOLD_MS);
    clearMessage();
  }

  // Show message
  function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.className = `pf-feedback-message ${type}`;
    messageEl.style.display = 'block';
    messageEl.setAttribute('role', 'alert');
    
    // Scroll to message
    messageEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // Clear message
  function clearMessage() {
    messageEl.style.display = 'none';
    messageEl.textContent = '';
    messageEl.className = 'pf-feedback-message';
  }

  // Update character count
  function updateCharCount() {
    const length = messageTextarea.value.length;
    charCountEl.textContent = length;
    
    if (length > MAX_MESSAGE_LENGTH) {
      charCountEl.style.color = '#ef4444';
    } else if (length > MAX_MESSAGE_LENGTH * 0.9) {
      charCountEl.style.color = '#f59e0b';
    } else {
      charCountEl.style.color = '#64748b';
    }
  }

  // Validate form
  function validateForm() {
    const message = messageTextarea.value.trim();
    
    if (!message) {
      showMessage('Please enter a message.', 'error');
      messageTextarea.focus();
      return false;
    }
    
    if (message.length < MIN_MESSAGE_LENGTH) {
      showMessage(`Message must be at least ${MIN_MESSAGE_LENGTH} characters.`, 'error');
      messageTextarea.focus();
      return false;
    }
    
    if (message.length > MAX_MESSAGE_LENGTH) {
      showMessage(`Message must be no more than ${MAX_MESSAGE_LENGTH} characters.`, 'error');
      messageTextarea.focus();
      return false;
    }
    
    // Validate email if provided
    const email = document.getElementById('pf-feedback-email').value.trim();
    if (email) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        showMessage('Please enter a valid email address.', 'error');
        document.getElementById('pf-feedback-email').focus();
        return false;
      }
    }
    
    return true;
  }

  // Set loading state
  function setLoading(loading) {
    submitBtn.disabled = loading;
    if (loading) {
      submitText.style.display = 'none';
      submitSpinner.style.display = 'inline-block';
    } else {
      submitText.style.display = 'inline';
      submitSpinner.style.display = 'none';
    }
  }

  // Submit feedback
  async function submitFeedback(e) {
    e.preventDefault();
    clearMessage();

    if (!validateForm()) {
      return;
    }

    const formData = {
      message: messageTextarea.value.trim(),
      page: getCurrentPage(),
      category: document.getElementById('pf-feedback-category').value.trim() || null,
      email: document.getElementById('pf-feedback-email').value.trim() || null
    };

    // Add user_id if available (from global variable or meta tag)
    if (typeof window.currentUserId !== 'undefined' && window.currentUserId) {
      formData.user_id = String(window.currentUserId);
    }

    setLoading(true);

    try {
      const response = await fetch(FEEDBACK_API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok && data.ok) {
        showMessage('Thank you for your feedback! We appreciate it.', 'success');
        form.reset();
        updateCharCount();
        
        // Close panel after 2 seconds
        setTimeout(() => {
          closePanel();
        }, 2000);
      } else {
        const errorMsg = data.error || 'Failed to send feedback. Please try again.';
        showMessage(errorMsg, 'error');
      }
    } catch (error) {
      console.error('Feedback submission error:', error);
      showMessage('Network error. Please check your connection and try again.', 'error');
    } finally {
      setLoading(false);
    }
  }

  // Event listeners
  if (btn) {
    btn.addEventListener('click', togglePanel);
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', closePanel);
  }

  if (backdrop) {
    backdrop.addEventListener('click', closePanel);
  }

  if (form) {
    form.addEventListener('submit', submitFeedback);
  }

  if (messageTextarea) {
    messageTextarea.addEventListener('input', updateCharCount);
  }

  // Close on escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && panel.getAttribute('aria-hidden') === 'false') {
      closePanel();
    }
  });


  // Initialize character count
  if (charCountEl && messageTextarea) {
    updateCharCount();
  }
})();
