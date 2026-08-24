/*
  FWRL shared site data.

  This file is the site's "database" — the public pages (index.html,
  standings.html, schedule.html, teams.html, discord.html) and
  fwrl-admin.html (admin dashboard) all load it. The admin dashboard can't
  write back to this file directly (a static site has no server to save to),
  so editing in the dashboard and clicking "Export data.js" downloads an
  updated copy of this exact file — replace this file on your host with the
  downloaded one to publish changes.
*/

var DISCORD_INVITE = "https://discord.gg/fwrl";

var TEAMS = [
  {name:"Voltage Motorsport", color:"#ff2e4d", drivers:["K. Reyes","M. Tanaka"], points:312},
  {name:"Ironclad Racing", color:"#00e0c6", drivers:["D. Novak","S. Osei"], points:298},
  {name:"Nightshift GP", color:"#ffd23f", drivers:["A. Marchetti","L. Kwon"], points:271},
  {name:"Redline Syndicate", color:"#8c7cff", drivers:["J. Ferreira","T. Vance"], points:244},
  {name:"Apex Collective", color:"#ff8a3d", drivers:["R. Dubois","N. Park"], points:219},
  {name:"Blacktop Union", color:"#4dd4ff", drivers:["E. Sato","C. Moreau"], points:187}
];

var STANDINGS = [
  {rank:1, driver:"K. Reyes", team:"Voltage Motorsport", color:"#ff2e4d", points:172},
  {rank:2, driver:"D. Novak", team:"Ironclad Racing", color:"#00e0c6", points:158},
  {rank:3, driver:"A. Marchetti", team:"Nightshift GP", color:"#ffd23f", points:149},
  {rank:4, driver:"M. Tanaka", team:"Voltage Motorsport", color:"#ff2e4d", points:140},
  {rank:5, driver:"S. Osei", team:"Ironclad Racing", color:"#00e0c6", points:140},
  {rank:6, driver:"J. Ferreira", team:"Redline Syndicate", color:"#8c7cff", points:126},
  {rank:7, driver:"L. Kwon", team:"Nightshift GP", color:"#ffd23f", points:122},
  {rank:8, driver:"R. Dubois", team:"Apex Collective", color:"#ff8a3d", points:109}
];

var SCHEDULE = [
  {round:1, name:"Season Opener", track:"Rocket Racing — Retail Row Loop", date:"Mar 14, 2026", status:"done"},
  {round:2, name:"Coastal Grand Prix", track:"Rocket Racing — Sunset Sands", date:"Apr 4, 2026", status:"done"},
  {round:3, name:"Desert Night Sprint", track:"Rocket Racing — Mirage Motors", date:"May 9, 2026", status:"done"},
  {round:4, name:"Highland Endurance", track:"Rocket Racing — Crank'd Up Circuit", date:"Jul 11, 2026", status:"live"},
  {round:5, name:"Metro Showdown", track:"Rocket Racing — Steel Farm Speedway", date:"Aug 15, 2026", status:"upcoming"},
  {round:6, name:"Season Finale", track:"Rocket Racing — Retail Row Loop", date:"Sep 26, 2026", status:"upcoming"}
];
