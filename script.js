// Shared behavior across all FWRL site pages: mobile nav toggle + the
// render functions each page calls for its own section (standings.html
// calls renderStandings(), etc — see the bottom of each page's HTML).
// Depends on data.js being loaded first (TEAMS / STANDINGS / SCHEDULE).

document.addEventListener("DOMContentLoaded", function () {
  var toggle = document.getElementById("menu-toggle");
  var mobileNav = document.getElementById("mobile-nav");
  if (toggle && mobileNav) {
    toggle.addEventListener("click", function () {
      mobileNav.classList.toggle("open");
    });
  }
});

function renderStandings() {
  var body = document.getElementById("standings-body");
  if (!body) return;
  var html = "";
  STANDINGS.forEach(function (s) {
    var rankClass = s.rank <= 3 ? "rank-" + s.rank : "";
    html +=
      "<tr>" +
      "<td class=\"" + rankClass + "\">" + s.rank + "</td>" +
      "<td>" + s.driver + "</td>" +
      "<td><span class=\"team-dot\" style=\"background:" + s.color + "\"></span>" + s.team + "</td>" +
      "<td>" + s.points + "</td>" +
      "</tr>";
  });
  body.innerHTML = html;
}

function renderSchedule() {
  var list = document.getElementById("schedule-list");
  if (!list) return;
  var label = { done: "Finished", live: "Live Now", upcoming: "Upcoming" };
  var cls = { done: "status-done", live: "status-live", upcoming: "status-upcoming" };
  var html = "";
  SCHEDULE.forEach(function (r) {
    html +=
      "<div class=\"race-row" + (r.status === "done" ? " done" : "") + "\">" +
      "<div class=\"race-num\">R" + r.round + "</div>" +
      "<div class=\"race-info\"><b>" + r.name + "</b><span>" + r.track + " · " + r.date + "</span></div>" +
      "<div class=\"race-status " + cls[r.status] + "\">" + label[r.status] + "</div>" +
      "</div>";
  });
  list.innerHTML = html;
}

function renderTeams() {
  var grid = document.getElementById("teams-grid");
  if (!grid) return;
  var html = "";
  TEAMS.forEach(function (t) {
    html +=
      "<div class=\"card\" style=\"border-top:3px solid " + t.color + "\">" +
      "<h3>" + t.name + "</h3>" +
      "<p>Drivers: " + t.drivers.join(" · ") + "</p>" +
      "<p style=\"margin-top:8px;color:" + t.color + ";font-weight:800\">" + t.points + " pts</p>" +
      "</div>";
  });
  grid.innerHTML = html;
}
