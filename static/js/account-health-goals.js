(function () {
  "use strict";

  var editor = document.getElementById(
    "pf-account-health-goal-editor"
  );
  if (!editor) return;

  var editButton = document.getElementById(
    "pf-account-health-goal-edit-button"
  );
  var form = document.getElementById(
    "pf-account-health-goal-editor-form"
  );
  var status = document.getElementById(
    "pf-account-health-goal-selection-status"
  );
  var error = document.getElementById(
    "pf-account-health-goal-editor-error"
  );
  var saveButton = document.getElementById(
    "pf-account-health-goal-save"
  );
  var closeButtons = Array.prototype.slice.call(
    editor.querySelectorAll("[data-account-health-goal-close]")
  );
  var checkboxes = Array.prototype.slice.call(
    editor.querySelectorAll('input[name="health_goals"]')
  );

  if (
    !editButton ||
    !form ||
    !status ||
    !error ||
    !saveButton ||
    !checkboxes.length
  ) {
    return;
  }

  var requiredCount = parseInt(
    editor.getAttribute("data-required-count") || "6",
    10
  );
  if (!Number.isFinite(requiredCount) || requiredCount < 1) {
    requiredCount = 6;
  }

  var knownValues = new Set(
    checkboxes.map(function (input) {
      return input.value;
    })
  );

  function uniqueKnownValues(values) {
    var uniqueValues = [];

    if (!Array.isArray(values)) return uniqueValues;

    values.forEach(function (value) {
      if (
        typeof value === "string" &&
        knownValues.has(value) &&
        uniqueValues.indexOf(value) === -1 &&
        uniqueValues.length < requiredCount
      ) {
        uniqueValues.push(value);
      }
    });

    return uniqueValues;
  }

  function readInitialSelection() {
    try {
      return uniqueKnownValues(
        JSON.parse(editor.getAttribute("data-selected-goals") || "[]")
      );
    } catch (_error) {
      return [];
    }
  }

  var selectedValues = readInitialSelection();
  if (!selectedValues.length) {
    selectedValues = uniqueKnownValues(
      checkboxes
        .filter(function (input) {
          return input.checked;
        })
        .map(function (input) {
          return input.value;
        })
    );
  }

  var initialSelection = selectedValues.slice();
  var isSaving = false;
  var lastFocusedElement = null;

  function setError(message) {
    error.textContent = message || "";
    error.hidden = !message;
  }

  function syncSelection() {
    var selectedCount = selectedValues.length;

    checkboxes.forEach(function (input) {
      var isSelected = selectedValues.indexOf(input.value) !== -1;
      var option = input.closest(".pf-account-health-goal-option");

      input.checked = isSelected;
      input.disabled = !isSelected && selectedCount >= requiredCount;

      if (option) {
        option.classList.toggle("is-selected", isSelected);
        option.classList.toggle("is-disabled", input.disabled);
      }
    });

    if (selectedCount === requiredCount) {
      status.textContent = (
        requiredCount + " of " + requiredCount + " selected."
      );
    } else {
      status.textContent = (
        selectedCount +
        " of " +
        requiredCount +
        " selected — choose " +
        (requiredCount - selectedCount) +
        " more."
      );
    }

    saveButton.disabled = isSaving || selectedCount !== requiredCount;
  }

  function resetSelection() {
    selectedValues = initialSelection.slice();
    setError("");
    syncSelection();
  }

  function openEditor() {
    if (isSaving) return;

    lastFocusedElement = document.activeElement;
    resetSelection();
    editor.hidden = false;
    editor.setAttribute("aria-hidden", "false");
    editButton.setAttribute("aria-expanded", "true");
    document.body.classList.add("pf-account-health-goal-editor-open");

    window.setTimeout(function () {
      var selectedInput = checkboxes.find(function (input) {
        return input.checked;
      });
      (selectedInput || closeButtons[0]).focus();
    }, 0);
  }

  function closeEditor() {
    if (isSaving) return;

    editor.hidden = true;
    editor.setAttribute("aria-hidden", "true");
    editButton.setAttribute("aria-expanded", "false");
    document.body.classList.remove("pf-account-health-goal-editor-open");

    if (
      lastFocusedElement &&
      typeof lastFocusedElement.focus === "function"
    ) {
      lastFocusedElement.focus();
    }
  }

  editButton.addEventListener("click", openEditor);

  closeButtons.forEach(function (button) {
    button.addEventListener("click", closeEditor);
  });

  editor.addEventListener("click", function (event) {
    if (event.target === editor) {
      closeEditor();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !editor.hidden) {
      closeEditor();
    }
  });

  checkboxes.forEach(function (input) {
    input.addEventListener("change", function () {
      var index = selectedValues.indexOf(input.value);

      if (input.checked && index === -1) {
        if (selectedValues.length < requiredCount) {
          selectedValues.push(input.value);
        } else {
          input.checked = false;
        }
      } else if (!input.checked && index !== -1) {
        selectedValues.splice(index, 1);
      }

      setError("");
      syncSelection();
    });
  });

  form.addEventListener("submit", async function (event) {
    event.preventDefault();

    if (selectedValues.length !== requiredCount || isSaving) {
      syncSelection();
      return;
    }

    isSaving = true;
    setError("");
    syncSelection();

    var headers = {
      "Content-Type": "application/json"
    };
    var csrfToken = document.querySelector(
      'meta[name="csrf-token"]'
    );

    if (csrfToken && csrfToken.content) {
      headers["X-CSRFToken"] = csrfToken.content;
    }

    try {
      var response = await fetch("/api/account-health-goals", {
        method: "PUT",
        credentials: "same-origin",
        headers: headers,
        body: JSON.stringify({
          health_goals: selectedValues
        })
      });

      var payload = {};
      try {
        payload = await response.json();
      } catch (_error) {
        payload = {};
      }

      if (!response.ok || !payload.success) {
        throw new Error(
          payload.message || "Your health goals could not be saved."
        );
      }

      window.location.reload();
    } catch (requestError) {
      isSaving = false;
      setError(
        requestError && requestError.message
          ? requestError.message
          : "Your health goals could not be saved."
      );
      syncSelection();
    }
  });

  syncSelection();
}());
