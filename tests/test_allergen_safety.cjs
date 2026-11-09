const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(
  path.join(root, 'templates/index.html'), 'utf8'
);
const card = fs.readFileSync(
  path.join(root, 'static/js/purefyul-share-card.js'), 'utf8'
);

const helperMarker =
  'window.pfSummarizeAllergenSignals = function(ingredients) {';

const helperStart = html.indexOf(helperMarker);
const helperEnd = html.indexOf('\n    };', helperStart);

assert.ok(helperStart >= 0 && helperEnd > helperStart);
assert.equal(html.indexOf(helperMarker, helperStart + 1), -1);

const helperSource = html.slice(
  helperStart, helperEnd + '\n    };'.length
);

const reportMarker = 'function displayAllergenResults(data) {';
const reportStart = html.indexOf(reportMarker);
const reportEnd = html.indexOf(
  'function initAllergenAccordions(', reportStart
);

assert.ok(reportStart >= 0 && reportEnd > reportStart);

const reportSource = html.slice(reportStart, reportEnd);

function makeContext() {
  const target = { innerHTML: '' };
  const context = {
    window: {},
    console: { log() {} },
    allergensResultsBodyEl: target,
    resultsBodyEl: target,
    pfIngredientPillHTML: (name) => String(name)
  };

  vm.runInNewContext(
    helperSource + '\n' +
    reportSource + '\n' +
    'globalThis.renderReport = displayAllergenResults;',
    context,
    { timeout: 1000 }
  );

  return { context, target };
}

function classify(ingredients) {
  const { context } = makeContext();
  return context.window.pfSummarizeAllergenSignals(ingredients);
}

function report(ingredients) {
  const { context, target } = makeContext();
  context.renderReport({ ingredients });
  return target.innerHTML;
}

const cases = [
  ['Greek yogurt', 'Greek Yogurt', ['Milk']],
  ['Almond milk', 'Almond Milk', ['Tree Nuts']],
  ['Soy milk', 'Soy Milk', ['Soy']],
  ['Peanut butter', 'Peanut Butter', ['Peanuts']],
  ['Eggplant', 'Eggplant', []],
  ['Unknown ingredient', 'Unknown Ingredient', []]
];

for (const [label, name, expected] of cases) {
  test('Classification: ' + label, () => {
    const result = classify([{ ingredient: name }]);

    assert.deepEqual(
      Array.from(result.names),
      expected
    );
  });
}

test('Backend Milk flag survives conflicting name', () => {
  const result = classify([{
    ingredient: 'Oat Milk',
    allergens: { name: 'Milk' }
  }]);

  assert.deepEqual(Array.from(result.names), ['Milk']);
  assert.equal(result.conflicts.length, 1);
});

test('Backend Eggs flag survives eggplant conflict', () => {
  const result = classify([{
    ingredient: 'Eggplant',
    allergens: { name: 'Eggs' }
  }]);

  assert.deepEqual(Array.from(result.names), ['Eggs']);
  assert.equal(result.conflicts.length, 1);
});

test('Report with missing flags is neutral', () => {
  const rendered = report([
    { ingredient: 'Unknown Ingredient' }
  ]);

  assert.match(rendered, /Allergen status unverified/);
  assert.match(rendered, /does not establish allergy safety/);
  assert.match(rendered, /pfa-verdict neutral/);
  assert.doesNotMatch(rendered, /pfa-verdict safe/);
  assert.doesNotMatch(rendered, /pfa-chip safe/);
});

test('Report preserves conflicting backend warnings', () => {
  const rendered = report([{
    ingredient: 'Oat Milk',
    allergens: { name: 'Milk' }
  }]);

  assert.match(rendered, /Potential allergens flagged/);
  assert.match(rendered, /Milk/);
  assert.match(rendered, /Conflicting ingredient flags/);
  assert.doesNotMatch(rendered, /passed checks for all 9/);
});

test('Report and result share the same classifier', () => {
  assert.match(
    html,
    /return window\.pfSummarizeAllergenSignals\(ingredients\)\.names;/
  );
  assert.doesNotMatch(
    html,
    /passed checks for all 9 major food allergens/
  );
});

// Extract a complete JS function while respecting template strings.
function extractFunction(text, signature) {
  const start = text.indexOf(signature);
  assert.ok(start >= 0);

  const open = text.indexOf('{', start);
  let depth = 0;
  let quote = null;
  let escaped = false;
  let lineComment = false;
  let blockComment = false;

  for (let i = open; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];

    if (lineComment) {
      if (ch === '\n') lineComment = false;
      continue;
    }

    if (blockComment) {
      if (ch === '*' && next === '/') {
        blockComment = false;
        i++;
      }
      continue;
    }

    if (quote) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === quote) quote = null;
      continue;
    }

    if (ch === '/' && next === '/') {
      lineComment = true;
      i++;
      continue;
    }

    if (ch === '/' && next === '*') {
      blockComment = true;
      i++;
      continue;
    }

    if (ch === '"' || ch === "'" || ch === '`') {
      quote = ch;
      continue;
    }

    if (ch === '{') depth++;

    if (ch === '}' && --depth === 0) {
      return text.slice(start, i + 1);
    }
  }

  throw new Error('Function closing brace not found');
}

const stripCode = extractFunction(
  card,
  'function buildAllergenStrip(allergenTitle) {'
);

const stripContext = {
  safeText: value => String(value ?? ''),
  escapeXml: value => String(value).replace(
    /[&<>"']/g,
    ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;',
      '"': '&quot;', "'": '&apos;'
    })[ch]
  ),
  truncateShareLabel: (value, max) =>
    String(value).slice(0, max)
};

vm.runInNewContext(
  stripCode + '\nglobalThis.renderStrip = buildAllergenStrip;',
  stripContext,
  { timeout: 1000 }
);

test('Share card displays potential allergens', () => {
  const svg = stripContext.renderStrip(
    'Potential allergens flagged: Milk, Soy'
  );

  assert.match(svg, />Potential<\/text>/);
  assert.match(svg, /Milk, Soy/);
});

test('Share card preserves historical warnings', () => {
  const svg = stripContext.renderStrip('Contains: Peanuts');

  assert.match(svg, />Potential<\/text>/);
  assert.match(svg, /Peanuts/);
});

test('Share card never presents unknown status as clear', () => {
  for (const label of [
    'Allergen status unverified — check ingredient labels.',
    'No major allergens identified from selected ingredient records.'
  ]) {
    const svg = stripContext.renderStrip(label);

    assert.match(svg, /unverified/i);
    assert.doesNotMatch(svg, /#F5F8F1/);
  }
});
