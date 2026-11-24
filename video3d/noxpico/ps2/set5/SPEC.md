# Version 5 set: Nox's loft workshop at night

## Why
The user's reference (a PS2-style 3D game cutscene: `../../study/work/me/ref/sheetA.png`, `sheetB.png`,
`../../study/reference.mp4`) shows realistic characters in a LARGE, believable, real-scale space (a gym with
floor-to-ceiling windows over a night city), lit softly: cool blue night ambience from the windows, warm practical
lights inside, soft shadows, real materials (painted steel, rubber, fabric, concrete, glass). Our previous set was a
small cartoon box (purple walls, pixel posters, toy proportions) where the characters looked huge. The new set must look
like a real place a 22-year-old electronics prodigy lives and works in: a converted industrial loft, slightly messy,
lived-in, with a big steel-framed window wall onto a city at night.

Target look: realistic game-cutscene (think PS2/PS3-era cinematic or a modern Blender/Unreal stylised-realistic
render), NOT cartoon, NOT pixel art, NOT saturated toy colours. Muted, natural palette; colour comes from light
(warm lamps vs blue night). Every object has bevelled edges, real-world dimensions, plausible materials with
roughness variation, and small imperfections (slightly rotated items, clutter, cables).

## Conventions (mandatory)
- Units metres, Z up. World origin on the floor in the middle of the room.
- Code lives in `ps2/set5/<module>.py`; run Blender as `../blender-venv/bin/python` from `ps2/`.
- Use the shared kit: `ps2/kit5.py` (Prop, box, cyl, sphere, torus, plane, tube, mesh, profile, light, place),
  materials `ps2/mat5.py` (`mat5.get(<library name>)` or the family functions `mat5.wood/matte/concrete/brick/metal/
  painted_metal/plastic/rubber/fabric/leather/glass/emissive/screen/paper/ceramic/plant/soil` for custom colours),
  render settings `ps2/look5.py` (`setup`, `world`, `camera`, `aim`, `area`, `preview`). Do NOT edit these three
  shared files (other people use them at the same time); put any extra helper or material in your own module.
- Props are built at the origin, standing on Z = 0, FRONT facing -Y, and expose `build(collection=None) -> kit5.Prop`.
  Placement in the room is done by the assembler (`kit5.place`), except for `arch` and `city` which are built in
  world coordinates.
- Images (screen contents, posters, labels) are generated with PIL into `ps2/lab/set5/tex/` and loaded with
  `bpy.data.images.load`. No downloads, no network, no brand logos, no text in other languages than French/English.
- Budget: the whole set < 1.5 M triangles. Cylinders 24-32 sides (12-16 for small parts), bevel segments 2.
- Previews: `../blender-venv/bin/python look5.py preview set5.<module> lab/set5/<module>_a.png <yaw> <elev>` for a prop
  (product shot on a floor). For arch/city write your own preview script with a camera inside the room. The CPU is
  shared by several builders: iterate at <= 512x512 and <= 32 samples (look5.preview uses 768x768 and 48: pass smaller
  sizes by calling look5.preview from your own script if you need speed), final check images at 768.
- LOOK at every preview with the Read tool and compare with the reference sheets. Iterate until the object reads as a
  real object at a glance. Typical failures to avoid: flat untextured colour, razor edges, floating objects, wrong scale,
  everything perfectly aligned, missing small parts that make an object recognisable (handles, screws, feet, cables).

## The room (world coordinates)
- Interior: x from -5.0 to +4.0 (9 m), y from -4.0 to +4.0 (8 m), floor z = 0, ceiling z = 3.4.
- Back wall y = +4.0: steel-framed industrial glazing from x = -5.0 to x = +2.0 (sill z = 0.70, head z = 3.15, black
  painted steel mullions about every 1.0 m, transom bars at z = 1.55 and 2.35, a few panes slightly different
  (one with a small opening vent)); x from +2.0 to +4.0 is old brick. A low concrete sill/ledge under the glazing.
- Left wall x = -5.0: old brick, painted off-white long ago and worn (mat5.brick painted).
- Right wall x = +4.0: plaster (warm grey). Entrance door in it: opening y from +0.75 to +1.70 (0.95 m wide), 2.10 m
  high, solid wood or painted steel door, frame, handle; the door swings INTO the room: hinge axis vertical at
  (x = 4.0, y = 1.70); closed, the free edge is at y = 0.75; opening rotates the leaf about the hinge so that the free
  edge comes into the room (x < 4); at 90 deg the leaf lies along y = 1.70 from x = 4.0 to x = 3.05. Expose the hinge as
  an empty (`door_hinge`, the leaf and its handle parented to it; rotation_euler.z = -radians(angle) opens it into the
  room, check it). Behind
  it a short corridor (x 4.0-6.5) with a warm wall lamp, a coat hook, visible when the door is open.
- Front wall y = -4.0: plaster, with a large framed print and a radiator (it is seen in reverse shots).
- Ceiling: concrete, two painted steel I-beams running along x at y = -1.0 and y = +2.0, an exposed round duct, conduit.
  Pendant lamps (industrial metal dome shades, warm bulbs, real lights): two above the workbench (x = -4.0 and -2.6,
  y = 3.3, bulb at z about 2.1), one above the living zone (x = 1.3, y = -1.4, z about 2.3).
- Floor: polished concrete (mat5 'concrete_floor'), a few darker stains; a large rug in the living zone.

## Zones and marks
- Nox's workstation along the glazing: workbench x from -4.6 to -1.7 (2.9 m long), depth 0.80 (back edge at the
  glazing y = 3.95, front edge y = 3.15), top height 0.78. Nox sits on a swivel stool at x = -3.1, y = 2.70 (seat
  height 0.52), facing +y (the window, his back to the room). He is right-handed: soldering station at his right
  (x about -2.6), the board in front of him (x -3.1, y 3.45), the desk lamp clamped near x = -2.3 lighting the work.
- Pico's run: she enters by the door (x = 4.0, y about 1.2) and runs to her mark (x = -1.55, y = 1.75): keep a clear
  lane y from 0.8 to 2.3 for x from -1.2 to 4.0 (nothing on the floor there).
- Living zone (front right): sofa centred x = 1.5, y = -2.3, facing +y (back to the front wall); coffee table in front
  (y = -1.3), rug under both, a floor lamp at the sofa's right end, a big plant.
- Left wall: tall steel shelving units x = -4.9 (against the wall) from y = -3.0 to y = +1.5, full of boxes, components,
  books, a 3D printer, robot parts; a pegboard with tools at x = -4.95, y = 2.2-3.3 above a small drawer cabinet.
- Back right (brick, x 2.0-4.0, y about 3.6): a small kitchenette counter (0.9 high) with an espresso machine,
  a kettle, a few mugs (Nox drinks black coffee), a small fridge.
- Pico's traces: a basketball, a skateboard leaning on the wall, a gym bag (she visits often).
- Bip, Nox's little drone (a palm-sized sphere-ish drone with a single camera eye and 4 tiny rotors), parked on a shelf.

## Lighting intent (the assembler sets the final lights; props must provide their own practical lights)
Night: ambient blue from the window (city glow and sky), warm pools from the pendant lamps and the desk lamp, a cooler
light in the corridor, small coloured LEDs (oscilloscope, soldering station, monitor glow). Practical light sources
must be real Blender lights inside the lamp + an emissive bulb/shade surface (so they glow on camera).
