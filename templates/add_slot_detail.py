content = open('templates/mealplanner.html').read()

# 1. Add detail popup HTML before </body>
popup_html = """
<!-- Slot Detail Popup -->
<div id="slot-detail-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:2000;align-items:flex-end;justify-content:center;">
  <div id="slot-detail-panel" style="background:#fff;border-radius:20px 20px 0 0;width:100%;max-width:520px;max-height:80vh;overflow-y:auto;padding:1.5rem;box-shadow:0 -4px 24px rgba(0,0,0,0.12);">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;">
      <div>
        <div id="sd-slot-label" style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#9AB5B3;margin-bottom:2px;"></div>
        <h3 id="sd-name" style="font-size:1.1rem;font-weight:700;color:#0f172a;margin:0;"></h3>
      </div>
      <button id="sd-close" style="background:#f1f5f9;border:none;border-radius:50%;width:32px;height:32px;cursor:pointer;font-size:1rem;color:#64748b;display:flex;align-items:center;justify-content:center;flex-shrink:0;">x</button>
    </div>
    <!-- Goal + Notes -->
    <div id="sd-meta" style="margin-bottom:1rem;display:flex;flex-wrap:wrap;gap:0.4rem;"></div>
    <!-- Nutrition -->
    <div id="sd-nutrition" style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:1rem;"></div>
    <!-- Ingredients -->
    <div id="sd-ings-wrap" style="margin-bottom:1.25rem;">
      <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#9AB5B3;margin-bottom:0.5rem;">Ingredients</div>
      <div id="sd-ings" style="display:flex;flex-wrap:wrap;gap:0.35rem;"></div>
    </div>
    <!-- Actions -->
    <div style="display:flex;gap:0.75rem;">
      <button id="sd-change" style="flex:1;padding:0.75rem;background:#0EA5A4;color:#fff;border:none;border-radius:10px;font-size:0.9rem;font-weight:700;cursor:pointer;font-family:inherit;">Change Smoothie</button>
      <button id="sd-remove" style="padding:0.75rem 1rem;background:#fff;color:#e53e3e;border:1.5px solid #e53e3e;border-radius:10px;font-size:0.9rem;font-weight:600;cursor:pointer;font-family:inherit;">Remove</button>
    </div>
  </div>
</div>
"""

content = content.replace('</body>', popup_html + '\n</body>')

# 2. Modify openDrawer to show detail popup for filled slots
old_open_drawer = """    function openDrawer(slotKey) {
      activeSlot = slotKey;
      const list = document.getElementById('drawerList');"""

new_open_drawer = """    function openDetailPopup(slotKey) {
      const assigned = slots[slotKey];
      if (!assigned) return;
      activeSlot = slotKey;

      // Find full recipe data
      const recipe = allRecipes.find(r => r.id === assigned.id) || {};
      const nutrition = recipe.nutrition_summary || {};
      const ingredients = recipe.ingredients || [];
      const [day, meal] = slotKey.split('-');

      // Populate popup
      document.getElementById('sd-slot-label').textContent = day + ' - ' + meal;
      document.getElementById('sd-name').textContent = assigned.name;

      // Meta (goal, notes)
      const meta = document.getElementById('sd-meta');
      meta.innerHTML = '';
      if (recipe.health_goal) {
        meta.innerHTML += '<span style="font-size:0.72rem;font-weight:600;background:#e6f7f7;color:#0B7F7E;padding:0.2rem 0.6rem;border-radius:100px;">' + escapeHtml(recipe.health_goal) + '</span>';
      }
      if (recipe.notes) {
        meta.innerHTML += '<span style="font-size:0.72rem;color:#64748b;">' + escapeHtml(recipe.notes) + '</span>';
      }

      // Nutrition boxes
      const nutWrap = document.getElementById('sd-nutrition');
      nutWrap.innerHTML = '';
      [['CAL', nutrition.calories, 'kcal'], ['PRO', nutrition.protein, 'g'], ['CARB', nutrition.carbs, 'g'], ['FAT', nutrition.fat, 'g']].forEach(function(n) {
        const val = (n[1] !== undefined && n[1] !== null && n[1] !== '') ? Math.round(n[1]) + '<span style="font-size:0.6rem;color:#0EA5A4;">' + n[2] + '</span>' : '-';
        nutWrap.innerHTML += '<div style="background:#f4fafa;border-radius:10px;padding:0.5rem;text-align:center;"><div style="font-size:1rem;font-weight:700;color:#1A3532;">' + val + '</div><div style="font-size:0.6rem;color:#6B8A87;text-transform:uppercase;letter-spacing:0.05em;">' + n[0] + '</div></div>';
      });

      // Ingredients
      const ingsWrap = document.getElementById('sd-ings');
      ingsWrap.innerHTML = '';
      if (ingredients.length) {
        ingredients.forEach(function(i) {
          const name = typeof i === 'object' ? (i.name || '') : i;
          const amt = typeof i === 'object' ? (i.totalGrams || i.portionGrams || '') : '';
          const unit = typeof i === 'object' ? (i.unit || 'g') : '';
          ingsWrap.innerHTML += '<span style="font-size:0.75rem;background:#f0f4f3;color:#2D5553;padding:0.2rem 0.6rem;border-radius:100px;border:1px solid #e0ecea;">' + escapeHtml(name) + (amt ? ' <span style="color:#9AB5B3;font-size:0.65rem;">' + Math.round(amt) + unit + '</span>' : '') + '</span>';
        });
      } else {
        ingsWrap.innerHTML = '<span style="font-size:0.8rem;color:#9AB5B3;">No ingredients recorded</span>';
      }

      // Show popup
      const overlay = document.getElementById('slot-detail-overlay');
      overlay.style.display = 'flex';

      // Wire buttons
      document.getElementById('sd-close').onclick = function() { overlay.style.display = 'none'; };
      document.getElementById('sd-change').onclick = function() { overlay.style.display = 'none'; openDrawer(slotKey); };
      document.getElementById('sd-remove').onclick = function() { delete slots[slotKey]; overlay.style.display = 'none'; buildGrid(); };
      overlay.onclick = function(e) { if (e.target === overlay) overlay.style.display = 'none'; };
    }

    function openDrawer(slotKey) {
      activeSlot = slotKey;
      const list = document.getElementById('drawerList');"""

content = content.replace(old_open_drawer, new_open_drawer)

# 3. Modify slot click to show detail popup for filled slots
old_click = """        slot.addEventListener('click', () => openDrawer(slot.dataset.slot));
        slot.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') openDrawer(slot.dataset.slot); });"""

new_click = """        slot.addEventListener('click', () => {
          const key = slot.dataset.slot;
          if (slots[key]) {
            openDetailPopup(key);
          } else {
            openDrawer(key);
          }
        });
        slot.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { const key = slot.dataset.slot; if (slots[key]) { openDetailPopup(key); } else { openDrawer(key); } } });"""

content = content.replace(old_click, new_click)

open('templates/mealplanner.html', 'w').write(content)
print('Done')
