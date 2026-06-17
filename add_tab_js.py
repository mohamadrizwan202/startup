content = open('templates/index.html').read()

# Add tab switcher HTML
old = '    <!-- Ingredient Analysis Tab Content -->\n    <div id="ingredient-tab-content"'
new = '''    <!-- Tab Switcher -->
    <div id="pf-main-tab-switcher" style="display:flex;gap:0;background:#fff;border-bottom:2px solid #e8f0ee;padding:0 1.5rem;">
      <button id="tab-btn-smoothie" style="padding:0.85rem 1.5rem;border:none;background:transparent;font-size:0.9rem;font-weight:600;color:#0EA5A4;border-bottom:2px solid #0EA5A4;margin-bottom:-2px;cursor:pointer;font-family:inherit;">&#x1F964; Build Smoothie</button>
      <button id="tab-btn-ingredient" style="padding:0.85rem 1.5rem;border:none;background:transparent;font-size:0.9rem;font-weight:600;color:#94a3b8;border-bottom:2px solid transparent;margin-bottom:-2px;cursor:pointer;font-family:inherit;">&#x1F957; Check Ingredient</button>
    </div>

    <!-- Ingredient Analysis Tab Content -->
    <div id="ingredient-tab-content"'''

content = content.replace(old, new)

# Add tab switching JS
tab_js = """
<script nonce="{{ csp_nonce }}">
(function() {
  function switchTab(tab) {
    var smoothieContent = document.getElementById('smoothie-tab-content');
    var ingredientContent = document.getElementById('ingredient-tab-content');
    var smoothieBtn = document.getElementById('tab-btn-smoothie');
    var ingredientBtn = document.getElementById('tab-btn-ingredient');
    if (!smoothieContent || !ingredientContent) return;

    if (tab === 'smoothie') {
      smoothieContent.classList.add('active');
      ingredientContent.classList.remove('active');
      smoothieBtn.style.color = '#0EA5A4';
      smoothieBtn.style.borderBottom = '2px solid #0EA5A4';
      ingredientBtn.style.color = '#94a3b8';
      ingredientBtn.style.borderBottom = '2px solid transparent';
    } else {
      ingredientContent.classList.add('active');
      smoothieContent.classList.remove('active');
      ingredientBtn.style.color = '#0EA5A4';
      ingredientBtn.style.borderBottom = '2px solid #0EA5A4';
      smoothieBtn.style.color = '#94a3b8';
      smoothieBtn.style.borderBottom = '2px solid transparent';
    }
  }

  document.addEventListener('DOMContentLoaded', function() {
    var smoothieBtn = document.getElementById('tab-btn-smoothie');
    var ingredientBtn = document.getElementById('tab-btn-ingredient');
    if (smoothieBtn) smoothieBtn.addEventListener('click', function() { switchTab('smoothie'); });
    if (ingredientBtn) ingredientBtn.addEventListener('click', function() { switchTab('ingredient'); });
  });

  window.switchTab = switchTab;
})();
</script>
"""

content = content.replace('</body>', tab_js + '\n</body>')
open('templates/index.html', 'w').write(content)
print('Done')
