// Tap32 – parametryczna obudowa (OpenSCAD)
// Części: "top" (płyta z otworami MX, okno OLED, otwór enkodera + ścianki),
//         "bottom" (dno z miejscem na płytkę i opcjonalnym pochyleniem), "both" (podgląd).
// Eksport STL:  openscad -D part=\"top\" -D board=\"kb2040\" -o top.stl tap32_case.scad

/* [Wybór] */
part  = "both";      // [top, bottom, both]
board = "kb2040";    // [kb2040, xiao_esp32s3]

/* [Klawisze MX] */
switch_hole = 14.0;  // otwór na przełącznik (14,0 mm; 13,9–14,1 zależnie od drukarki)
pitch       = 19.05; // rozstaw klawiszy
plate_t     = 1.5;   // grubość płyty w miejscu zatrzasków MX
margin      = 5.0;   // margines wokół siatki

/* [Górny pas: OLED i enkoder] */
top_band       = 25.0;          // głębokość pasa nad klawiszami
oled_module    = [38.0, 12.0];  // płytka modułu OLED 0.91"
oled_window    = [24.0, 7.0];   // widoczne okno (obszar aktywny ok. 22,4×5,6 mm)
oled_window_dx = 2.0;           // przesunięcie okna względem środka modułu (taśma po prawej)
oled_x         = 4.0;           // odległość modułu od lewej krawędzi siatki
enc_hole       = 7.2;           // otwór na tuleję M7 EC11
enc_tab        = false;         // wycięcie na wypust antyobrotowy EC11
enc_x_from_right = 14.0;        // środek enkodera od prawej krawędzi siatki
enc_plate_t    = 2.0;           // grubość płyty przy enkoderze (≤ 2–3 mm, tuleja ma ~5 mm gwintu)

/* [Obudowa] */
wall        = 2.4;
inner_h     = 13.0;   // wysokość wnętrza pod płytą (MX ~8,5 mm z pinami, EC11 ~7 mm, płytka + USB)
corner_r    = 3.0;
bottom_t    = 2.0;
screw       = "M2";   // [M2, M3]
boss_d      = 6.0;
tilt_deg    = 0;      // opcjonalne pochylenie (klin pod dnem), np. 6
usb_cut     = [11.0, 5.5];  // wycięcie USB-C w tylnej ściance (szer. × wys.)
usb_z       = 2.5;    // wysokość dolnej krawędzi wycięcia nad dnem (grubość podstawki płytki)

/* [Płytki] */
// [szerokość (X), długość (Y, wzdłuż USB)] – XIAO 21×17,8 mm, KB2040 ok. 33×18 mm
function board_size(b) = b == "xiao_esp32s3" ? [17.8, 21.0] : [18.0, 33.0];
board_tol = 0.4;
board_x_from_left = 0;  // 0 = pod środkiem

$fn = 48;

// ---------------------------------------------------------------- wymiary pochodne
grid_w = 3 * pitch;
grid_d = 3 * pitch;
W = grid_w + 2 * margin;
D = grid_d + top_band + 2 * margin;
H = inner_h + plate_t;
screw_d   = screw == "M3" ? 3.4 : 2.4;   // otwór przelotowy w dnie
screw_pil = screw == "M3" ? 2.6 : 1.7;   // otwór pod wkręt w słupku
screw_head = screw == "M3" ? 6.0 : 4.2;
bsize = board_size(board) + [board_tol, board_tol];

grid_x0 = margin;
grid_y0 = margin;                // klawisze z przodu (y = 0 to przód)
band_y0 = margin + grid_d;       // górny pas z tyłu
band_cy = band_y0 + top_band / 2;

oled_cx = grid_x0 + oled_x + oled_module[0] / 2;
enc_cx  = grid_x0 + grid_w - enc_x_from_right;

boss_inset = wall + boss_d / 2 - 0.6;
boss_pos = [
    [boss_inset, boss_inset], [W - boss_inset, boss_inset],
    [boss_inset, D - boss_inset], [W - boss_inset, D - boss_inset],
];

module rounded_box(size, r) {
    hull() for (x = [r, size[0] - r], y = [r, size[1] - r])
        translate([x, y, 0]) cylinder(r = r, h = size[2]);
}

// ---------------------------------------------------------------- górna część
module switch_holes() {
    for (r = [0:2], c = [0:2])
        translate([grid_x0 + (c + 0.5) * pitch, grid_y0 + (2 - r + 0.5) * pitch, -1])
            translate([-switch_hole / 2, -switch_hole / 2, 0])
                cube([switch_hole, switch_hole, H + 2]);
}

module oled_cutouts() {
    // okno w płycie
    translate([oled_cx + oled_window_dx - oled_window[0] / 2, band_cy - oled_window[1] / 2, -1])
        cube([oled_window[0], oled_window[1], H + 2]);
}

module oled_guides() {
    // ramka prowadząca moduł od spodu (moduł przyklejany / dociskany)
    g = 1.2;
    h = 3.0;
    translate([0, 0, H - plate_t - h])
    difference() {
        translate([oled_cx - oled_module[0] / 2 - g - 0.3, band_cy - oled_module[1] / 2 - g - 0.3, 0])
            cube([oled_module[0] + 2 * g + 0.6, oled_module[1] + 2 * g + 0.6, h]);
        translate([oled_cx - oled_module[0] / 2 - 0.3, band_cy - oled_module[1] / 2 - 0.3, -1])
            cube([oled_module[0] + 0.6, oled_module[1] + 0.6, h + 2]);
        // przerwa na złącze/przewody
        translate([oled_cx - 6, band_cy - oled_module[1] / 2 - g - 1, -1]) cube([12, g + 2, h + 2]);
    }
}

module encoder_cutouts() {
    translate([enc_cx, band_cy, -1]) cylinder(d = enc_hole, h = H + 2);
    if (enc_tab)
        translate([enc_cx - 0.7, band_cy + 7.0, H - plate_t - 1]) cube([1.4, 2.6, plate_t + 2]);
}

module encoder_pad() {
    // pogrubienie płyty wokół enkodera do enc_plate_t (ale nie więcej)
    if (enc_plate_t > plate_t)
        translate([enc_cx, band_cy, H - enc_plate_t]) cylinder(d = 16, h = enc_plate_t - plate_t + 0.01);
}

module top() {
    difference() {
        union() {
            difference() {
                rounded_box([W, D, H], corner_r);
                translate([wall, wall, -1]) cube([W - 2 * wall, D - 2 * wall, H - plate_t + 1]);
            }
            for (p = boss_pos) translate([p[0], p[1], 0]) cylinder(d = boss_d, h = H - plate_t);
            oled_guides();
            encoder_pad();
            // żebro między pasem a klawiszami (sztywność)
            translate([wall, band_y0 - 0.6, H - plate_t - 2]) cube([W - 2 * wall, 1.2, 2]);
        }
        switch_holes();
        oled_cutouts();
        encoder_cutouts();
        for (p = boss_pos) translate([p[0], p[1], -1]) cylinder(d = screw_pil, h = H - plate_t - 1);
        // wycięcie USB-C w tylnej ściance
        translate([board_cx() - usb_cut[0] / 2, D - wall - 1, usb_z])
            cube([usb_cut[0], wall + 2, usb_cut[1]]);
    }
}

// ---------------------------------------------------------------- dolna część
function board_cx() = board_x_from_left > 0 ? board_x_from_left : W / 2;

module board_holder() {
    // ramka na płytkę przy tylnej ściance, USB-C skierowane do tyłu
    h = usb_z;
    y1 = D - wall - 0.2;
    difference() {
        translate([board_cx() - bsize[0] / 2 - 1.6, y1 - bsize[1] - 1.6, 0])
            cube([bsize[0] + 3.2, bsize[1] + 1.6, h + 1.6]);
        translate([board_cx() - bsize[0] / 2, y1 - bsize[1], h]) cube([bsize[0], bsize[1] + 2, 5]);
        // miejsce na elementy pod płytką
        translate([board_cx() - bsize[0] / 2 + 1.5, y1 - bsize[1] + 1.5, -1])
            cube([bsize[0] - 3, bsize[1] - 1.5, h + 2]);
    }
}

module wedge() {
    if (tilt_deg > 0) {
        rise = D * tan(tilt_deg);
        hull() {
            translate([0, 0, -0.01]) rounded_box([W, 1, 0.01], 0.4);
            translate([0, D - 1, -rise]) rounded_box([W, 1, rise], 0.4);
        }
    }
}

module bottom() {
    difference() {
        union() {
            rounded_box([W, D, bottom_t], corner_r);
            translate([0, 0, bottom_t]) board_holder();
            // kołnierz wchodzący w górną część
            translate([wall + 0.3, wall + 0.3, bottom_t])
                difference() {
                    cube([W - 2 * wall - 0.6, D - 2 * wall - 0.6, 2]);
                    translate([1.2, 1.2, -1]) cube([W - 2 * wall - 3, D - 2 * wall - 3, 4]);
                    // przerwy na słupki
                    for (p = boss_pos) translate([p[0] - wall - 0.3, p[1] - wall - 0.3, -1])
                        cylinder(d = boss_d + 1, h = 4);
                    // przerwa na płytkę/USB
                    translate([board_cx() - wall - usb_cut[0], D - 2 * wall - 4, -1]) cube([2 * usb_cut[0], 5, 4]);
                }
            wedge();
        }
        for (p = boss_pos) {
            translate([p[0], p[1], -50]) cylinder(d = screw_d, h = 100);
            translate([p[0], p[1], -50]) cylinder(d = screw_head, h = 50 + 1.2);  // łeb wpuszczony
        }
    }
}

// ---------------------------------------------------------------- wybór części
if (part == "top") {
    // do druku: płytą w dół
    translate([0, D, H]) rotate([180, 0, 0]) top();
} else if (part == "bottom") {
    bottom();
} else {
    color("SlateGray") bottom();
    color("Gainsboro", 0.9) translate([0, 0, bottom_t]) top();
}

echo(str("Tap32: płytka=", board, ", wymiary zewn. ", W, " × ", D, " × ", H + bottom_t, " mm"));
