content = open('templates/home_public.html').read()

# Fix 1: Price $7 -> $4.99
content = content.replace(
    '<span class="amt">$7</span><span class="per"> / month</span>',
    '<span class="amt">$4.99</span><span class="per"> / month</span>'
)

# Fix 2: Remove features not built yet, keep only what exists
old_pro_features = """          <li><span class="fck">✓</span> Everything in Free</li>
          <li><span class="fck">✓</span> Save unlimited custom recipes</li>
          <li><span class="fck">✓</span> Weekly smoothie meal planner</li>
          <li><span class="fck">✓</span> Grocery list export</li>
          <li><span class="fck">✓</span> Family multi-profile mode</li>
          <li><span class="fck">✓</span> Nutrition trend history</li>
          <li><span class="fck">✓</span> Priority support</li>
          <li><span class="fck">✓</span> Early access to new features</li>"""

new_pro_features = """          <li><span class="fck">✓</span> Everything in Free</li>
          <li><span class="fck">✓</span> Save unlimited custom recipes</li>
          <li><span class="fck">✓</span> Weekly smoothie meal planner</li>
          <li><span class="fck">✓</span> Export recipes as CSV</li>
          <li><span class="fck">✓</span> Recipe detail popup in meal planner</li>
          <li><span class="fck">✓</span> Priority support</li>
          <li><span class="fck">✓</span> Early access to new features</li>"""

content = content.replace(old_pro_features, new_pro_features)

# Fix 3: Hero CTA - change "Open App" to "Try Free"
content = content.replace(
    '<a href="/register" class="btn btn-white btn-lg">Open App</a>',
    '<a href="/register" class="btn btn-white btn-lg">Try Free →</a>'
)

# Fix 4: Final CTA button
content = content.replace(
    '<a href="/register" class="btn btn-white btn-lg">Create your free account →</a>',
    '<a href="/app" class="btn btn-white btn-lg">Start Building Free →</a>'
)

# Fix 5: Replace fake testimonials with honest early access section
old_testimonials = """<!-- TESTIMONIALS -->
<section class="section proof-section">
  <div class="container">
    <div class="section-header">
      <p class="section-label">Early Users</p>
      <h2>People blending smarter with PureFyul</h2>
    </div>
    <div class="proof-grid">
      <div class="proof-card">
        <div class="stars">★★★★★</div>
        <p class="proof-q">"I was always guessing whether the spinach amount was right for my 4-year-old. PureFyul just tells me. That confidence alone is worth it."</p>
        <div class="proof-author">
          <div class="proof-av">SA</div>
          <div>
            <div class="proof-name">Sara A.</div>
            <div class="proof-meta">Mother of two · Phoenix, AZ</div>
          </div>
        </div>
      </div>
      <div class="proof-card">
        <div class="stars">★★★★★</div>
        <p class="proof-q">"The muscle recovery preset changed my post-workout routine. I was under-eating protein in my smoothies by a lot. Now the breakdown feels intentional."</p>
        <div class="proof-author">
          <div class="proof-av">MK</div>
          <div>
            <div class="proof-name">Marcus K.</div>
            <div class="proof-meta">Fitness trainer · Atlanta, GA</div>
          </div>
        </div>
      </div>
      <div class="proof-card">
        <div class="stars">★★★★★</div>
        <p class="proof-q">"My mom is 71 and her doctor said to watch her sugar. PureFyul's senior profile keeps things in check automatically. Didn't have to do any of the math."</p>
        <div class="proof-author">
          <div class="proof-av">LR</div>
          <div>
            <div class="proof-name">Laila R.</div>
            <div class="proof-meta">Caregiver · Dallas, TX</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>"""

new_early_access = """<!-- EARLY ACCESS -->
<section class="section proof-section">
  <div class="container">
    <div class="section-header">
      <p class="section-label">Now Live</p>
      <h2>PureFyul is free to use today</h2>
      <p>No credit card. No setup. Just pick your age group and start building.</p>
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;max-width:900px;margin:0 auto;">
      <div class="proof-card" style="text-align:center;padding:2rem 1.5rem;">
        <div style="font-size:2.5rem;margin-bottom:0.75rem;">🥤</div>
        <h3 style="font-size:1rem;font-weight:700;color:#111;margin-bottom:0.5rem;">30+ Preset Smoothies</h3>
        <p style="font-size:0.875rem;color:#666;line-height:1.6;">Ready-made blends organized by health goal. Load any preset in one tap.</p>
      </div>
      <div class="proof-card" style="text-align:center;padding:2rem 1.5rem;">
        <div style="font-size:2.5rem;margin-bottom:0.75rem;">👨‍👩‍👧</div>
        <h3 style="font-size:1rem;font-weight:700;color:#111;margin-bottom:0.5rem;">Every Age Group</h3>
        <p style="font-size:0.875rem;color:#666;line-height:1.6;">From toddlers to seniors — portions auto-adjust for each age group automatically.</p>
      </div>
      <div class="proof-card" style="text-align:center;padding:2rem 1.5rem;">
        <div style="font-size:2.5rem;margin-bottom:0.75rem;">📅</div>
        <h3 style="font-size:1rem;font-weight:700;color:#111;margin-bottom:0.5rem;">Weekly Meal Planner</h3>
        <p style="font-size:0.875rem;color:#666;line-height:1.6;">Plan your whole week. Assign saved smoothies to any meal slot. Pro feature.</p>
      </div>
    </div>
  </div>
</section>"""

content = content.replace(old_testimonials, new_early_access)

# Fix 6: Remove onclick attributes from age pills (CSP violation)
# Replace with data attributes only - JS will be updated to use event delegation
content = content.replace(
    'onclick="setAge(\'toddler\')"', ''
).replace(
    'onclick="setAge(\'child\')"', ''
).replace(
    'onclick="setAge(\'teen\')"', ''
).replace(
    'onclick="setAge(\'adult\')"', ''
).replace(
    'onclick="setAge(\'senior\')"', ''
)

# Fix 7: Update demo JS to use event delegation instead of onclick
old_js = "  document.querySelectorAll('a[href^=\"#\"]').forEach(a =>"
new_js = """  // Age pill event delegation (CSP-safe)
  document.querySelectorAll('.age-pill').forEach(function(pill) {
    pill.addEventListener('click', function() {
      setAge(pill.getAttribute('data-age'));
    });
  });

  document.querySelectorAll('a[href^="#"]').forEach(a =>"""

content = content.replace(old_js, new_js)

open('templates/home_public.html', 'w').write(content)
print('Done')
