const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(
  path.join(__dirname, '../templates/mealplanner.html'),
  'utf8'
);

const clearMarker =
  "document.getElementById('clearBtn').addEventListener(";
const saveMarker = "async function savePlan() {";
const saveButtonMarker =
  "document.getElementById('saveBtn').addEventListener('click', savePlan);";

const clearStart = html.indexOf(clearMarker);
const saveStart = html.indexOf(saveMarker, clearStart);
const saveButtonStart = html.indexOf(saveButtonMarker, saveStart);

assert.ok(clearStart >= 0, 'Clear Week handler missing');
assert.ok(saveStart > clearStart, 'savePlan function missing');
assert.ok(saveButtonStart > saveStart, 'Save button binding missing');

const script =
  html.slice(clearStart, saveStart) +
  html.slice(
    saveStart,
    saveButtonStart + saveButtonMarker.length
  );

function harness(mode = 'success', confirmed = true) {
  const state = {
    mode,
    confirmed,
    requests: [],
    alerts: [],
    gridBuilds: 0,
    finishFetch: null
  };

  const handlers = {};
  const elements = {
    clearBtn: { disabled: false },
    saveBtn: {},
    saveToast: { style: { display: 'none' } }
  };

  for (const [id, element] of Object.entries(elements)) {
    element.addEventListener = (event, fn) => {
      assert.equal(event, 'click');
      handlers[id] = fn;
    };
  }

  const context = {
    document: {
      getElementById(id) {
        assert.ok(elements[id], 'Unexpected DOM element: ' + id);
        return elements[id];
      }
    },
    confirm: () => state.confirmed,
    alert: message => state.alerts.push(message),
    buildGrid: () => { state.gridBuilds++; },
    getWeekDates: () => [new Date('2026-11-09T12:00:00Z')],
    setTimeout: () => {},
    fetch: (url, options) => {
      state.requests.push({
        url,
        method: options.method,
        body: JSON.parse(options.body)
      });

      if (state.mode === 'network-error') {
        return Promise.reject(new Error('Network unavailable'));
      }

      if (state.mode === 'deferred') {
        return new Promise(resolve => {
          state.finishFetch = resolve;
        });
      }

      return Promise.resolve({
        ok: state.mode === 'success'
      });
    }
  };

  vm.createContext(context);

  vm.runInContext(`
    let slots = {
      'Mon-Breakfast': { id: 7, name: 'Test Smoothie' }
    };
    let weekOffset = 0;

    ${script}

    globalThis.snapshot = () => ({
      slots: JSON.parse(JSON.stringify(slots)),
      weekOffset
    });

    globalThis.navigateDuringSave = () => {
      weekOffset = 1;
      slots = {
        'Tue-Lunch': { id: 8, name: 'Other Week Smoothie' }
      };
    };
  `, context, { timeout: 1000 });

  assert.equal(typeof handlers.clearBtn, 'function');
  assert.equal(typeof handlers.saveBtn, 'function');

  return {
    state,
    elements,
    context,
    clear: () => handlers.clearBtn(),
    save: () => handlers.saveBtn(),
    snapshot: () => context.snapshot()
  };
}

test('Clear Week saves an empty week to the existing API', async () => {
  const h = harness();
  await h.clear();

  assert.equal(Object.keys(h.snapshot().slots).length, 0);
  assert.equal(h.state.requests.length, 1);

  const request = h.state.requests[0];

  assert.equal(request.url, '/api/mealplans');
  assert.equal(request.method, 'POST');
  assert.equal(request.body.week_start, '2026-11-09');
  assert.deepEqual(request.body.slots, {});
  assert.equal(h.state.gridBuilds, 1);
  assert.equal(h.elements.clearBtn.disabled, false);
  assert.equal(h.elements.saveToast.style.display, 'block');
  assert.equal(h.state.alerts.length, 0);
});

test('Canceling confirmation preserves the calendar', async () => {
  const h = harness('success', false);
  const before = h.snapshot();

  await h.clear();

  assert.deepEqual(h.snapshot(), before);
  assert.equal(h.state.requests.length, 0);
  assert.equal(h.state.gridBuilds, 0);
  assert.equal(h.state.alerts.length, 0);
});

test('HTTP failure restores previous selections', async () => {
  const h = harness('http-error');
  const before = h.snapshot();

  await h.clear();

  assert.deepEqual(h.snapshot(), before);
  assert.equal(h.state.requests.length, 1);
  assert.equal(h.state.gridBuilds, 2);
  assert.equal(h.elements.clearBtn.disabled, false);
  assert.match(h.state.alerts[0], /restored/i);
});

test('Network failure restores previous selections', async () => {
  const h = harness('network-error');
  const before = h.snapshot();

  await h.clear();

  assert.deepEqual(h.snapshot(), before);
  assert.equal(h.state.requests.length, 1);
  assert.equal(h.state.gridBuilds, 2);
  assert.equal(h.elements.clearBtn.disabled, false);
  assert.match(h.state.alerts[0], /restored/i);
});

test('Failed save does not overwrite a different week', async () => {
  const h = harness('deferred');

  const operation = h.clear();

  assert.equal(h.elements.clearBtn.disabled, true);
  assert.equal(h.state.requests.length, 1);

  h.context.navigateDuringSave();
  const otherWeek = h.snapshot();

  h.state.finishFetch({ ok: false });
  await operation;

  assert.deepEqual(h.snapshot(), otherWeek);
  assert.equal(h.elements.clearBtn.disabled, false);
  assert.match(h.state.alerts[0], /return to that week/i);
});

test('Existing Save Plan button still saves selected slots', async () => {
  const h = harness();

  await h.save();

  assert.equal(h.state.requests.length, 1);
  assert.equal(
    h.state.requests[0].body.slots['Mon-Breakfast'].id,
    7
  );
  assert.equal(h.elements.saveToast.style.display, 'block');
});
