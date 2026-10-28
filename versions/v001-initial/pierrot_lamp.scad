// Pierrot shadow lamp.
//
// A box shaped like Pierrot's face. The lid is the face with the painted
// eyes; inside, an LED hangs face-down from the ceiling at lamp_height and
// shines through holes in the walls, drawing the rest of the character
// (cap, hair, ruff, body, bells) on the table in light and shadow.
//
// Units: mm. Origin on the table, right under the LED; +y is "up" in the
// drawing. The geometry of the picture comes from generated/pierrot_data.scad,
// written by tools/make_data.py (see README).
//
// The holes: a wall point at height z lights the table point scaled by
// h / (h - z) from the axis, so the set of all lit rays is exactly
// linear_extrude(height = h, scale = 0) of the lit table area. Subtracting
// that cone from the wall cuts every hole, tapered along its rays.

include <generated/pierrot_data.scad>

part = "assembly"; // [assembly, shell, ceiling, lid, lid_ink, projection, none]

/* [Light] */
// Height of the LED emitter above the table. The data was cleaned for PD_LAMP_HEIGHT.
lamp_height = PD_LAMP_HEIGHT;
// From the emitter up to the underside of the ceiling.
ceiling_gap = 22;
// Show the light cone in the assembly (preview only).
show_light = false;

/* [Shell] */
wall = PD_WALL;
// Solid band at the foot of the wall.
base_h = PD_BASE;
ceiling_t = 4.5;
// Width of the ledge the ceiling rests on.
ledge_w = 2.5;
// Clearance around the drop-in ceiling.
fit = 0.3;

/* [LED holder] */
// Board diameter: a 20 mm "star" LED board by default.
led_d = 20;
led_fit = 0.4;
// How deep the board sits in its pocket.
led_pocket = 2.2;
// The emitter sits this far below the board face (dome / lens height).
emitter_drop = 1.5;
holder_wall = 2;
holder_back = 1.6;
stem_d = 11;
stem_bore = 4.5;

/* [Wire] */
rib_w = 7;
rib_depth = 6;
wire_d = 3.4;
groove_depth = 2.5;

/* [Lid] */
lid_t = 3;
// Depth of the black inlay (eyes, outline); also the paint recess.
ink_depth = 0.6;
// Black rim along the edge of the lid.
ink_rim = 1.2;
pin_d = 4;
pin_h = 3;
pin_fit = 0.3;

/* [Hidden] */
cone_eps = 0.01;
$fn = 64;

z_board = lamp_height + emitter_drop;          // LED board face (facing down)
z_ceil = lamp_height + ceiling_gap;            // ceiling underside
shell_h = z_ceil + ceiling_t;
cup_d = led_d + led_fit + 2 * holder_wall;
cup_top = z_board + led_pocket + holder_back;
taper_top = cup_top + (cup_d - stem_d) / 2;    // 45 deg, prints upside down
wire_ang = atan2(-PD_WIRE[1], -PD_WIRE[0]);    // inward, toward the axis
wire_in = wall + rib_depth / 2;                // bore centre, from the outer wall
wire_xy = PD_WIRE + wire_in * [cos(wire_ang), sin(wire_ang)];

assert(taper_top < z_ceil, "LED holder does not fit under the ceiling: raise ceiling_gap");
assert(groove_depth < ceiling_t - 1, "wire groove cuts through the ceiling");
assert(PD_Z_TOP < lamp_height, "holes above the LED: the data does not match lamp_height");
if (lamp_height != PD_LAMP_HEIGHT)
    echo(str("WARNING: lamp_height ", lamp_height, " differs from the data (", PD_LAMP_HEIGHT,
             "); rerun tools/make_data.py --lamp-height ", lamp_height));

echo(str("LAMP: emitter z=", lamp_height, "; ceiling z=", z_ceil, "; shell height=", shell_h,
         "; lid on top=", shell_h + lid_t));
echo(str("PICTURE: x ", PD_EXTENT[0], "..", PD_EXTENT[2], "; y ", PD_EXTENT[1], "..", PD_EXTENT[3],
         "; holes up to z=", PD_Z_TOP));

// ---------------------------------------------------------------- 2D -----

module outline() polygon(PD_LID);
module light_2d() polygon(PD_LIGHT_POINTS, PD_LIGHT_PATHS);
// The painted parts plus an even black rim (the face's outline in the drawing),
// closed up so the ink never just touches the edge of the lid.
module ink_2d()
    intersection() {
        outline();
        offset(r = -0.4) offset(r = 0.4) union() {
            polygon(PD_INK_POINTS, PD_INK_PATHS);
            difference() { offset(delta = 1) outline(); offset(delta = -ink_rim) outline(); }
        }
    }

module ring_2d() difference() { outline(); offset(delta = -wall) outline(); }

module rib_2d()
    intersection() {
        offset(delta = -wall / 2) outline();
        translate(PD_WIRE) rotate(wire_ang)
            translate([-1, -rib_w / 2]) square([wall + rib_depth + 1, rib_w]);
    }

// ---------------------------------------------------------------- 3D -----

// Every ray from the LED that lands on a lit part of the table.
module light_cone()
    translate([0, 0, -0.01])
        linear_extrude(height = lamp_height * (1 - cone_eps), scale = cone_eps)
            light_2d();

module led_holder() {
    translate([0, 0, z_board]) cylinder(d = cup_d, h = cup_top - z_board);
    translate([0, 0, cup_top]) cylinder(d1 = cup_d, d2 = stem_d, h = taper_top - cup_top);
    translate([0, 0, cup_top]) cylinder(d = stem_d, h = z_ceil - cup_top + 0.01);
}

// The wire runs across the top of the ceiling (and the top of the rib).
module wire_groove()
    translate([0, 0, shell_h - groove_depth])
        linear_extrude(groove_depth + 1) hull() {
            circle(d = wire_d);
            translate(wire_xy) circle(d = wire_d);
        }

// 45-degree ledge inside the top of the wall that the ceiling rests on.
module ledge() {
    n = ceil(ledge_w / 0.2);
    for (i = [0 : n - 1])
        translate([0, 0, z_ceil - ledge_w + i * ledge_w / n])
            linear_extrude(ledge_w / n + 0.01) difference() {
                offset(delta = -wall + 0.01) outline();
                offset(delta = -wall - (i + 1) * ledge_w / n) outline();
            }
}

// Printed as it stands: the holes' lower edges sit on the solid foot and
// only their upper edges, which follow the drawing, have to bridge.
module shell() {
    difference() {
        union() {
            difference() {
                linear_extrude(shell_h) ring_2d();
                light_cone();
            }
            linear_extrude(base_h) ring_2d();
            linear_extrude(shell_h) rib_2d();
            ledge();
        }
        // wire: up the rib, out at the foot through a slot
        translate([wire_xy[0], wire_xy[1], -1]) cylinder(d = wire_d, h = shell_h + 2);
        translate([wire_xy[0], wire_xy[1], -1]) rotate(wire_ang + 180)
            translate([0, -wire_d / 2, 0]) cube([wire_in + 2, wire_d, wire_d + 1.5]);
        wire_groove();
    }
}

module ceiling_2d()
    difference() {
        offset(delta = -wall - fit) outline();
        offset(delta = fit) rib_2d();
    }

// Drops in from the top onto the ledge; carries the LED face-down at lamp_height.
module ceiling() {
    difference() {
        union() {
            translate([0, 0, z_ceil]) linear_extrude(ceiling_t) ceiling_2d();
            led_holder();
        }
        translate([0, 0, z_board - 1]) cylinder(d = led_d + led_fit, h = led_pocket + 1);
        translate([0, 0, z_board]) cylinder(d = stem_bore, h = shell_h);
        wire_groove();
        for (p = PD_PINS)
            translate([p[0], p[1], shell_h - pin_h - 0.5]) cylinder(d = pin_d + pin_fit, h = pin_h + 1);
    }
}

// Lid as used: bottom face on z = 0, face up.
module lid_body() {
    difference() {
        linear_extrude(lid_t) outline();
        translate([0, 0, lid_t - ink_depth]) linear_extrude(ink_depth + 1) ink_2d();
    }
    for (p = PD_PINS)
        translate([p[0], p[1], -pin_h]) cylinder(d = pin_d, h = pin_h + 0.01);
}

module lid_ink() translate([0, 0, lid_t - ink_depth]) linear_extrude(ink_depth) ink_2d();

// Print orientation: shell as it stands, ceiling on its top face (stem up),
// lid on its face. lid and lid_ink share coordinates, so their two STLs drop
// straight into one multi-material job.
module flip(h) rotate([180, 0, 0]) translate([0, 0, -h]) children();

module assembly() {
    color("#2b2b30") shell();
    color("#3a3a40") ceiling();
    translate([0, 0, shell_h]) {
        color("#f4f1ea") lid_body();
        color("#111") lid_ink();
    }
    color("gold") translate([0, 0, lamp_height]) sphere(d = 3);
    if (show_light) %light_cone();
    color("#e8e2d0", 0.35) translate([0, 0, -0.6]) linear_extrude(0.5) light_2d();
}

if (part == "assembly") assembly();
else if (part == "shell") shell();
else if (part == "ceiling") flip(shell_h) ceiling();
else if (part == "lid") flip(lid_t) lid_body();
else if (part == "lid_ink") flip(lid_t) lid_ink();
else if (part == "projection") { light_2d(); outline(); }
