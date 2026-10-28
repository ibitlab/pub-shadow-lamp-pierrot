// Pierrot shadow lamp.
//
// A box shaped like Pierrot's face. The lid is the face with the painted
// eyes and an even black outline; inside, an LED set face-down into the
// ceiling shines through holes in the walls, drawing the rest of the
// character (cap, hair, ruff, body, bells) on the table in light and shadow.
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

part = "assembly"; // [assembly, shell, shell_print, supports, ceiling, lid, lid_ink, lid_2color, pins, projection, none]

/* [Light] */
// Height of the LED emitter above the table. The data was cleaned for PD_LAMP_HEIGHT.
lamp_height = PD_LAMP_HEIGHT;
// Show the light cone in the assembly (preview only).
show_light = false;

/* [Shell] */
wall = PD_WALL;
// Solid band at the foot of the wall.
base_h = PD_BASE;
ceiling_t = 6;
// Width of the ledge the ceiling rests on.
ledge_w = 2.5;
// Clearance around the drop-in ceiling.
fit = 0.3;

/* [LED] */
// Board diameter: a 20 mm "star" LED board by default.
led_d = 20;
led_fit = 0.4;
// How deep the board sits in its pocket in the underside of the ceiling.
led_pocket = 2.2;
// The emitter sits this far below the board face (dome / lens height).
emitter_drop = 1.5;
// Holes for the two wires from the board's front pads, at the pocket's edge.
pad_hole = 2.5;

/* [Wire] */
rib_w = 7;
rib_depth = 6;
wire_d = 3.4;
groove_depth = 2.5;

/* [Lid] */
lid_t = 3.5;
// Depth of the black inlay (eyes, outline); also the paint recess.
ink_depth = 0.6;
// Width of the black outline along the edge of the lid.
ink_rim = PD_RIM;
// Colours written into the two-colour 3MF (part = "lid_2color").
lid_color = "white";
ink_color = "black";

/* [Pins] */
// Separate locating pins, glued into the ceiling; the lid drops over them.
pin_d = 4;
// Length glued into the ceiling.
pin_glue = 4;
// Length sticking up into the lid.
pin_h = 1.8;
// Gap for glue in the ceiling, on the diameter.
glue_gap = 0.2;
// Loose fit in the lid, on the diameter.
pin_fit = 0.3;
pin_chamfer = 0.4;

/* [Print supports] */
// Wall of a support tube: one extrusion line.
support_line = 0.4;
// Air gap between a support's top and the part it holds: one layer.
support_gap = PD_LAYER[1];
// Clearance from the sides of a hole, measured on the table (much less on the wall).
support_clear = 0.3;

/* [Hidden] */
cone_eps = 0.01;
$fn = 64;

z_ceil = lamp_height + emitter_drop;           // ceiling underside = LED board face
shell_h = z_ceil + ceiling_t;
wire_ang = atan2(-PD_WIRE[1], -PD_WIRE[0]);    // inward, toward the axis
wire_in = wall + rib_depth / 2;                // bore centre, from the outer wall
wire_xy = PD_WIRE + wire_in * [cos(wire_ang), sin(wire_ang)];
// The pads sit across the board; the holes straddle the pocket wall, so the
// wires can pass the board's edge notches.
pads = [for (s = [-1, 1]) (led_d + led_fit) / 2 * [cos(wire_ang + 90 * s), sin(wire_ang + 90 * s)]];

lid_socket = pin_h + 0.4;                      // the lid sits on the ceiling, not on the pins

assert(led_pocket + groove_depth < ceiling_t - 1, "LED pocket and wire groove meet: thicken the ceiling");
assert(pin_glue + 0.3 < ceiling_t - 1, "pin socket too deep for the ceiling");
assert(lid_socket < lid_t - ink_depth - 0.5, "pin socket shows through the lid: thicken the lid");
assert(PD_Z_TOP < lamp_height, "holes above the LED: the data does not match lamp_height");
if (lamp_height != PD_LAMP_HEIGHT)
    echo(str("WARNING: lamp_height ", lamp_height, " differs from the data (", PD_LAMP_HEIGHT,
             "); rerun tools/make_data.py --lamp-height ", lamp_height));

echo(str("LAMP: emitter z=", lamp_height, "; shell height=", shell_h,
         "; with lid=", shell_h + lid_t));
echo(str("PICTURE: x ", PD_EXTENT[0], "..", PD_EXTENT[2], "; y ", PD_EXTENT[1], "..", PD_EXTENT[3],
         "; holes up to z=", PD_Z_TOP));

// ---------------------------------------------------------------- 2D -----

module outline() polygon(PD_LID);
module light_2d() polygon(PD_LIGHT_POINTS, PD_LIGHT_PATHS);
// The eyes plus an even black outline along the edge, closed up so the ink
// never just touches the edge of the lid.
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

// The wires run across the top of the ceiling: from both pad holes to the
// centre, and on to the rib.
module wire_groove()
    translate([0, 0, shell_h - groove_depth])
        linear_extrude(groove_depth + 1) {
            hull() for (p = pads) translate(p) circle(d = wire_d);
            hull() { circle(d = wire_d); translate(wire_xy) circle(d = wire_d); }
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

// ------------------------------------------------------- print supports -----
//
// The generator prints the wall layer by layer and lists every place where a
// layer would start in mid-air (or hang out too far). Each gets a tube with
// a single-line wall inside its hole: the piece of wall ring between two rays
// from the LED, hollowed to support_line. Clipping it with the light cone
// lowered by support_gap makes its top follow the underside of the part one
// layer below it (easy to snap off) and sinks its foot into whatever is
// under it. The tube stays a hair inside the wall's faces and the hole's
// sides (support_clear): faces that merely touch would leave the merged mesh
// pinched, and slicers then drop the open loops.

module support_footprint(p)
    intersection() {
        difference() {
            offset(delta = -0.05) outline();
            offset(delta = -wall + 0.05) outline();
        }
        polygon(concat([[0, 0]], [for (i = [0 : 4]) let (a = p[0] + (p[1] - p[0]) * i / 4)
                                  500 * [cos(a), sin(a)]]));
    }

module supports()
    intersection() {
        union() for (p = PD_SUPPORTS)
            translate([0, 0, p[2]]) linear_extrude(p[3] - p[2]) difference() {
                support_footprint(p);
                offset(delta = -support_line) support_footprint(p);
            }
        translate([0, 0, -support_gap])
            linear_extrude(height = lamp_height * (1 - cone_eps), scale = cone_eps)
                offset(delta = -support_clear) light_2d();
    }

module ceiling_2d()
    difference() {
        offset(delta = -wall - fit) outline();
        offset(delta = fit) rib_2d();
    }

// Drops in from the top onto the ledge. The LED board sits in a pocket in
// its underside, face down, so the emitter ends up at lamp_height.
module ceiling() {
    difference() {
        translate([0, 0, z_ceil]) linear_extrude(ceiling_t) ceiling_2d();
        translate([0, 0, z_ceil - 1]) cylinder(d = led_d + led_fit, h = led_pocket + 1);
        for (p = pads) translate([p[0], p[1], z_ceil - 1]) cylinder(d = pad_hole, h = ceiling_t + 2);
        wire_groove();
        for (p = PD_PINS)
            translate([p[0], p[1], shell_h - pin_glue - 0.3]) socket(pin_d + glue_gap, pin_glue + 0.3);
    }
}

// Blind hole opening at its top, with a lead-in chamfer.
module socket(d, depth) {
    cylinder(d = d, h = depth + 0.01);
    translate([0, 0, depth - pin_chamfer]) cylinder(d1 = d, d2 = d + 2 * pin_chamfer, h = pin_chamfer + 0.01);
    translate([0, 0, depth]) cylinder(d = d + 2 * pin_chamfer, h = 1);
}

// One pin, standing on its end; chamfered both ends.
module pin() {
    l = pin_glue + pin_h;
    c = pin_chamfer;
    cylinder(d1 = pin_d - 2 * c, d2 = pin_d, h = c);
    translate([0, 0, c]) cylinder(d = pin_d, h = l - 2 * c);
    translate([0, 0, l - c]) cylinder(d1 = pin_d, d2 = pin_d - 2 * c, h = c);
}

// Lid as used: bottom face on z = 0, face up. Flat underneath apart from the
// pin sockets, so it prints either way up without supports.
module lid_body() {
    difference() {
        linear_extrude(lid_t) outline();
        translate([0, 0, lid_t - ink_depth]) linear_extrude(ink_depth + 1) ink_2d();
        for (p = PD_PINS)
            translate([p[0], p[1], lid_socket]) mirror([0, 0, 1]) socket(pin_d + pin_fit, lid_socket);
    }
}

module lid_ink() translate([0, 0, lid_t - ink_depth]) linear_extrude(ink_depth) ink_2d();

// Print orientation: shell as it stands, ceiling on its top face (pocket up),
// lid on its face. lid and lid_ink share coordinates, so their two STLs drop
// straight into one multi-material job.
module flip(h) rotate([180, 0, 0]) translate([0, 0, -h]) children();

module assembly() {
    color("#2b2b30") shell();
    color("#3a3a40") ceiling();
    for (p = PD_PINS) color("#888") translate([p[0], p[1], shell_h - pin_glue]) pin();
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
else if (part == "shell_print") { shell(); supports(); }
else if (part == "supports") supports();
else if (part == "ceiling") flip(shell_h) ceiling();
else if (part == "lid") flip(lid_t) lid_body();
else if (part == "lid_ink") flip(lid_t) lid_ink();
else if (part == "lid_2color") {
    // Two separate bodies in one 3MF (export with --enable=lazy-union):
    // the slicer gets one part per filament, already in place.
    flip(lid_t) color(lid_color) lid_body();
    flip(lid_t) color(ink_color) lid_ink();
}
else if (part == "pins") for (i = [0 : len(PD_PINS) - 1]) translate([i * (pin_d + 5), 0, 0]) pin();
else if (part == "projection") { light_2d(); outline(); }
