(function () {
  "use strict";

  var picker = document.getElementById("account-health-goal-picker");
  var status = document.getElementById("health-goal-selection-status");

  if (!picker || !status) {
    return;
  }

  var requiredCount = Number(picker.dataset.requiredCount || "6");
  var checkboxes = Array.prototype.slice.call(
    picker.querySelectorAll('input[name="health_goals"]')
  );

  if (!Number.isFinite(requiredCount) || requiredCount < 1 || !checkboxes.length) {
    return;
  }

  function updateSelectionState() {
    var selectedCount = checkboxes.filter(function (checkbox) {
      return checkbox.checked;
    }).length;
    var selectionIsFull = selectedCount >= requiredCount;

    status.textContent =
      selectedCount + " of " + requiredCount + " selected";
    status.classList.toggle(
      "is-complete",
      selectedCount === requiredCount
    );

    checkboxes.forEach(function (checkbox) {
      var disableCheckbox = selectionIsFull && !checkbox.checked;
      var option = checkbox.closest(".health-goal-option");

      checkbox.disabled = disableCheckbox;

      if (option) {
        option.classList.toggle("is-unavailable", disableCheckbox);
        option.setAttribute(
          "aria-disabled",
          disableCheckbox ? "true" : "false"
        );
      }
    });
  }

  checkboxes.forEach(function (checkbox) {
    checkbox.addEventListener("change", updateSelectionState);
  });

  updateSelectionState();
}());
