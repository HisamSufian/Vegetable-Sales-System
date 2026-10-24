// Small helper for the search-as-you-type dropdowns (works together with htmx).

function choosePicker(picker, id, label) {
  picker.querySelector(".picker-value").value = id;
  picker.querySelector(".picker-input").value = label;
  picker.querySelector(".picker-results").innerHTML = "";
  picker.dispatchEvent(new CustomEvent("picker:chosen", { bubbles: true, detail: { id: id, label: label } }));
}

// Tapping a result picks it.
document.addEventListener("click", function (e) {
  var option = e.target.closest(".picker-option[data-id]");
  if (option) {
    choosePicker(option.closest(".picker"), option.dataset.id, option.dataset.label);
  }
});

// Typing again clears the previous choice, so an old id is never sent by mistake.
document.addEventListener("input", function (e) {
  if (e.target.classList.contains("picker-input")) {
    e.target.closest(".picker").querySelector(".picker-value").value = "";
  }
});

// After "+ Add", the server answers with the new profile; select it automatically.
document.addEventListener("htmx:afterSwap", function (e) {
  var chosen = e.target.querySelector && e.target.querySelector(".picker-chosen");
  if (chosen) {
    choosePicker(e.target.closest(".picker"), chosen.dataset.id, chosen.dataset.label);
  }
});

// Close an open dropdown when tapping elsewhere.
document.addEventListener("click", function (e) {
  document.querySelectorAll(".picker").forEach(function (p) {
    if (!p.contains(e.target)) { p.querySelector(".picker-results").innerHTML = ""; }
  });
});
