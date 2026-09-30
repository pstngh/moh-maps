# Recreating a scene from a picture

How to turn a screenshot or photo the user sends into a MOHAA map that looks
like it. Worked example: `maps/mk_ref_room`, a room from stock mohdm1 rebuilt
from one 1280×720 screenshot, without looking at `mohdm1.map`.

![reference | recreation | blend](images/ref_room_compare.jpg)

Left: the reference (stock mohdm1). Middle: `mk_ref_room` at `-q preview`.
Right: 50/50 blend; edges that line up mean the camera and geometry match.

## 1. Read the picture

List what you see, near to far: surfaces (floor, walls, ceiling, beams),
openings (doors, windows, arches), fixtures and props (lamps, furniture,
trees), the light (sun direction, lamps, colour), and what's visible outside.
Decide what's playable space and what's backdrop.

## 2. Fix the camera

For a MOHAA screenshot the camera is known: eye 82 units above the floor
(standing), fov 80, usually a level view. For a photo, estimate the eye height
(about 60 units per metre: a door is ~112–128 tall, a player 94, a storey
128–192, a window ~56×80) and the vertical field of view (phone main camera
≈ 50–55° in landscape). Look for the horizon: level lines converge on the
row at eye height. If it isn't the middle row, the camera is pitched.

Put the camera at the origin in `build.py`: eye `(0, 0, eye)`, yaw 0, so the
view looks along +x and image-left is +y. Then every measurement below lands
directly in map coordinates.

## 3. Measure with `mohkit.camera`

```python
from mohkit.camera import Camera
cam = Camera(1280, 720)            # or Camera(w, h, vfov=52, eye=70) for a photo
d = cam.floor_depth(530)           # where a wall meets the floor (row 530) -> 276 units away
cam.lateral(170, d)                # that wall's corner (column 170) -> +227 (left)
cam.height(263, d)                 # a door top on that wall -> 129
cam.depth_from_lateral(990, -77)   # a point on a side wall 77 units to the right -> 126 deep
cam.project((276, 81, 128))        # check a guess: back to pixels
```

The floor line of each wall gives its depth; corners give lateral positions;
heights follow. Side walls: first find their offset from a corner, then use
`depth_from_lateral` for features along them (the far jamb of a window gives the
wall thickness). Beams and ceilings: `ceiling_depth(row, z)`. Write every
measurement in the build.py docstring (see `maps/mk_ref_room/build.py`).

## 4. Pick materials

1. `python -m mohkit looks-like ref.png --box x0,y0,x1,y1 --where wall -o sheet.png`
   ranks the ~1,400 stock AA materials by lighting-tolerant features and writes a
   swatch sheet with your crop first. It narrows the field; it does not decide.
   On test crops the right material ranked 1–62, so the answer is usually on
   the sheet. It is weak on small, dark, warmly lit crops.
2. `python -m mohkit swatches stone cobble -o sheet.png` shows every retail
   texture whose name contains a word (including ones no stock map uses).
3. Compare **at the same physical size**: estimate the size of one stone,
   plank or brick in units from the picture, and pick the texture scale that
   gives the same size (texel size = scale). `fort_floor_cobbleflttile` at
   0.375 matched stones of about 25×14 units.
4. Check colour against the light: reference colour ÷ light colour ≈ albedo.
   A mismatch is often the texture (too red, too grey), not the lighting.
5. Resolution matters: a 64-px texture magnified to fit shows as smeared blobs.
   If the reference is crisp, the original was higher-resolution.

## 5. Build it

Block out with the `Carver` (one air box per room or yard; windows and openings
as small air boxes through the wall), then `kit.door`/`kit.window` for
openings with images, `b.box` for beams, trims and bars, and `b.prop` for
fixtures (`mohkit.props.search("bulb")`). Put a `Shot` at the reference camera
first in `SHOTS`, plus a couple of others to check the spaces. Add at least one
spawn. Work at `-q draft` (seconds for a room).

## 6. Compare and iterate

```sh
python -m mohkit build maps/x -q preview
python -m mohkit compare ref.png ~/Library/Caches/mohkit/build/homes/x/main/screenshots/00_reference.png \
    -o cmp.png --region back=560,280,790,520 --region floor=150,560,700,700
```

`compare` writes reference | shot | blend. In the blend, misaligned edges show
up as double lines: fix the geometry first. Then `--region` prints mean colours
and the brightness ratio per region (> 1: the shot is too dark there). Tune
lights and `ambientlight` until the ratios are within about 1.0–1.4, but judge
lighting only on `preview` or `normal` builds (draft has no bounce light).

Lessons from mk_ref_room:

- A surface facing the camera but lit in the reference needs a light on the
  camera's side: the room continues behind the camera, and so do its lamps.
- Outside seen through a window: tall yard walls with a low sun leave the view in
  shadow. Use a bigger yard, and put the sun where it lights what the window shows
  but its patch through the window stays out of frame.
- Vertical walls get little sunlight from a high sun (cos of the elevation).

## Results for mk_ref_room

Six build iterations, about 10 minutes of compile time in total. Geometry lines up
in the blend: back wall, door, both beams, window jamb, floor line, bulb and cabinet.
Brightness per region is within 1.0–1.4 of the reference except the door, which is
2× too bright because the chosen door texture is lighter than the original. The wall
texture is slightly redder than the original. Regenerate the reference with:

```python
from mohkit import game
game.run([], "dm/mohdm1", [game.Shot("ref", (-288, 1240, 130), (0, 0, 0))], run_name="ref_c8")
```
