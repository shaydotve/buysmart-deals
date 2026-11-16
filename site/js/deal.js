(function () {
  var hero = document.getElementById("hero-img");
  document.querySelectorAll(".thumbs button").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!hero) return;
      hero.src = button.getAttribute("data-src");
      document.querySelectorAll(".thumbs button").forEach(function (other) {
        other.removeAttribute("aria-current");
      });
      button.setAttribute("aria-current", "true");
    });
  });
})();
