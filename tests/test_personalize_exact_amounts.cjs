// Untouched editor fields must send their exact amounts, not the rounded
// numbers shown on screen; otherwise "Update Smoothie" with no changes
// shifts calories by about 1 kcal and spends a credit.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const html = fs.readFileSync('templates/index.html', 'utf8');
const start = html.indexOf('function pfGetPersonalizeSetupIngredientSelections(');
const end = html.indexOf('function pfGetPersonalizeRecipeGoal(', start);
assert(start > 0 && end > start, 'selection collector not found');

function makeRow(id, name, input) {
  return {
    dataset: { ingredientId: id, ingredientName: name },
    querySelector: () => input,
  };
}

function makeInput(exact, shown) {
  return {
    value: shown,
    dataset: { exactAmount: String(exact), displayedAmount: shown },
  };
}

const beets = makeInput(57.143, '57');
const kiwi = makeInput(101.25, '101');
const host = {
  dataset: { seeded: '1' },
  querySelectorAll: () => [
    makeRow('beets', 'Beets', beets),
    makeRow('kiwi', 'Kiwi', kiwi),
  ],
};

const context = {
  document: { getElementById: (id) =>
    id === 'pf-personalize-setup-ingredients' ? host : null },
};
vm.createContext(context);
vm.runInContext(html.slice(start, end), context);

// 1. Nothing touched: exact amounts go to the server.
let result = context.pfGetPersonalizeSetupIngredientSelections({});
assert.strictEqual(
  JSON.stringify(result.selections.map((s) => s.amount)), '[57.143,101.25]',
  'untouched fields must send exact amounts'
);

// 2. The user edits one field: that field sends what they typed.
kiwi.value = '110';
result = context.pfGetPersonalizeSetupIngredientSelections({});
assert.strictEqual(
  JSON.stringify(result.selections.map((s) => s.amount)), '[57.143,110]',
  'an edited field must send the typed amount'
);

// 3. The submit code refuses to update when nothing changed.
assert(
  html.includes('No changes yet. Change an amount or add an ingredient first.'),
  'unchanged-update guard missing'
);

console.log('PASS — exact amounts kept for untouched fields; edits honored; no-change guard present');
