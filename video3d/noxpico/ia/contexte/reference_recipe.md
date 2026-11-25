# Production recipe from the two reference videos

Both sketches are built from very short shots: the longest is 5.83 s, none exceeds 8 s or 10 s, so any current video model can generate every shot in one go. A two-character remake needs 6 start images (8 with a prop angle and a cameo).

I could not listen to the audio; everything about sound is inferred from loudness and spectra. Speaker attribution comes from lips and captions.

## 1. Files

| | reference.mp4 (gym) | reference2.mp4 (bakery) |
|---|---|---|
| Duration | 39.66 s, of which the film is 0–35.62 s; the rest is the TikTok end card | 63.50 s, no end card |
| Picture | 774x576 (4:3), 24 fps, h264, ~433 kb/s | 768x576 (4:3), 30 fps, h264, ~549 kb/s |
| Audio | AAC 44.1 kHz stereo, 128 kb/s, −17.5 LUFS, LRA 6.9 LU, peak 0 dBFS | AAC 44.1 kHz stereo, 32 kb/s, −18.8 LUFS, LRA 3.4 LU, peak −4.7 dBFS |
| Stereo | near mono (L/R correlation 0.97) | near mono (0.98) |

How each was made (inferred):

- **reference.mp4 reads as real keyframed 3D.**
  - Shots 5, 7 and 11 contain runs of mathematically identical frames (up to 34 frames, 1.4 s) between lines.
  - 11 of 13 cameras are perfectly locked.
  - Props, logo, scar and the lit basilica sit in consistent places across all angles.
- **reference2.mp4 reads as AI image-to-video.**
  - Every shot has continuous micro-motion and no frozen frames.
  - The source is about 24 unique frames per second retimed to 30.
  - Signage is gibberish ("Cekcaisfaen", "Cnaire") and the bakery layout changes with each angle.
  - The curly woman's necklace changes between set-ups, the hoodie lettering morphs within a shot, and Zak's blush fades in.
  - Shots 4 and 8 start from the same still image.

## 2. Shot list: reference.mp4 (13 shots)

Characters: Zak (calm; silver-green hair, green tracksuit), Red (excitable; ginger, denim jacket), a bodybuilder, Zak's mother.

| # | Time (s) | Dur | Framing, who is on screen | Who talks (line) | Camera | Action |
|---|---|---|---|---|---|---|
| 1 | 0.00–3.17 | 3.17 | Two-shot, chest up, eye level: Zak left, Red right, bodybuilder benching behind | Red: "Frérot, en vrai de vrai…" / "Il soulève combien, lui ?" | static | Red turns to Zak; Zak impassive |
| 2 | 3.17–7.08 | 3.92 | Over both shoulders onto the bodybuilder | Zak, mouth unseen: "SubhanAllah la puissance." | static | Bodybuilder presses a huge bar; grunt |
| 3 | 7.08–8.67 | 1.58 | Close-up Red, frontal | Red: "Et moi, et moi, Zak ?" | static | Pout snaps to anger; points at himself |
| 4 | 8.67–12.17 | 3.50 | Medium, Red from behind at the dumbbell rack; ends as a two-shot | Red: "Et ça, c'est la puissance ?" | eased pan/truck left, about a third of the frame width | Walks, grabs a dumbbell, curls; pan reveals Zak |
| 5 | 12.17–15.67 | 3.50 | Over Red's shoulder onto Zak, chest up | Zak: "Sah ?" / "Nan wallah." | static | Looks at the dumbbell, looks up, deadpan |
| 6 | 15.67–17.54 | 1.87 | Wide profile: Red on the bench, Zak full figure behind, arms crossed | Red: "Et avec la barre ?!" | static | Red lies down and grips the bar |
| 7 | 17.54–20.12 | 2.58 | Medium close Zak, frontal, arms crossed | Zak: "Hakallah ma mère soulève plus." | static | Almost no movement |
| 8 | 20.12–21.33 | 1.21 | Medium close Red, low angle, wide lens | Red: "Je prends la même barre que lui." | static | Sits up, points at the lens |
| 9 | 21.33–25.00 | 3.67 | Wide, same set-up as 6 | Red, face hidden: "Haychik frérot… aide-moi !" | static | Bar pins him; Zak does not move |
| 10 | 25.00–28.54 | 3.54 | Medium on the mother; Red lying in front, bodybuilder behind | Mother: "Hagoun houa." | static | Lifts the bar with one hand, shopping bag in the other |
| 11 | 28.54–31.58 | 3.04 | Close-up Red lying, from above | Red: "Mash'Allah la puissance." | static | Wide-eyed awe, nearly frozen |
| 12 | 31.58–33.04 | 1.46 | Wide frontal, symmetrical; becomes medium as he sits up | Red: "Elle soulève combien, ta mère ?!" | static | Sits up fast |
| 13 | 33.04–35.62 | 2.58 | Extreme close-up Zak | Zak: "Allahou a3lam." | slow push-in, roughly +20% | 1.4 s silent stare, line, faint smirk |

## 3. Shot list: reference2.mp4 (27 shots)

Characters: Zak (never speaks), Damien the baker (pinstripe suit, red tie, white apron; opens every line with "Mm."), a curly-haired woman (orange turtleneck), a wavy-haired woman (navy top), Marlon (bleached crop, black hoodie).

Each shot carries exactly one line: 27 lines in 27 shots.

| # | Time (s) | Dur | Framing, who is on screen | Who talks (line) | Camera | Action |
|---|---|---|---|---|---|---|
| 1 | 0.00–3.43 | 3.43 | Wide: curly woman left, Zak and baker behind the counter | Curly: "Damien, who is THIS?! He's been standing there since I came in!" | slow pan, ~8% of width | Steps in, points at Zak |
| 2 | 3.43–9.27 | 5.83 | Two-shot: Zak left, baker right | Baker: "Mm. That's Zak. C'est juste une jeune racaille de cité. Sa mère l'envoie acheter une baguette." | static | Arm round Zak, pats his head |
| 3 | 9.27–12.20 | 2.93 | Medium single, baker | Baker: "Anyway. Last baguette of the day." | static | Lifts a baguette up to the lens |
| 4 | 12.20–14.43 | 2.23 | Close-up, curly woman | Curly: "MINE! I've been waiting ten minutes!" | slight drift | Raises her hand |
| 5 | 14.43–16.57 | 2.13 | Two-shot: Zak in front, wavy woman behind | Wavy: "I called this morning! It's reserved!" | slight drift | Holds up her phone |
| 6 | 16.57–19.23 | 2.67 | Close-up, curly woman | Curly: "Reserved?! Since when do bakeries take reservations?!" | slight reframing | Dismay to anger; a 2–3 frame snap at 17.43 |
| 7 | 19.23–21.60 | 2.37 | Close-up baker, Zak behind, baguette in front | Baker: "Mm. Since this morning. Elle a été très polie." | static | Smirk |
| 8 | 21.60–23.07 | 1.47 | Close-up, curly woman (same start image as 4) | Curly: "I'm VERY polite!" | slight drift | Hand on chest |
| 9 | 23.07–25.03 | 1.97 | Same set-up as 7 | Baker: "Mm. You screamed "mine"." | static | Deadpan |
| 10 | 25.03–26.70 | 1.67 | Over the baker's shoulder onto Zak and the wavy woman | Wavy: "Thank you. Wrap it, please." | slow drift | Gestures at the baguette on the counter |
| 11 | 26.70–31.17 | 4.47 | Medium frontal, baker behind the counter | Baker: "Mm. One moment. The reservation is not in your name." | static | 1 s silent look down, then the line |
| 12 | 31.17–32.80 | 1.63 | Close-up, wavy woman | Wavy: "What?! Whose name is it?!" | push-in | Leans in |
| 13 | 32.80–34.73 | 1.93 | Over Zak's shoulder onto the baker | Baker: "Mm. "La mère de Zak."" | static | Zak scratches his head |
| 14 | 34.73–36.37 | 1.63 | Two-shot, curly woman and Zak, frontal | Curly: "HIS MOTHER reserved it?!" | slight drift | Points at Zak; his face turns red |
| 15 | 36.37–38.50 | 2.13 | Close-up, wavy woman | Wavy: "She called before me?!" | she leans, slight tilt | Hands on hips |
| 16 | 38.50–41.00 | 2.50 | Over the wavy woman's and Zak's shoulders onto the baker | Baker: "Mm. She calls every morning. Six fifty-nine." | near static | Zak rubs his neck |
| 17 | 41.00–43.13 | 2.13 | Two-shot: baker in profile, Zak blushing | Baker: "Mm. Zak. Tu as l'argent ?" | slight drift | Baker holds out his hand; Zak shows coins |
| 18 | 43.13–44.43 | 1.30 | Close-up curly woman with Zak's open palm of coins in front | Curly: "That's eighty cents!" | fast reframe at the start | Points at the coins |
| 19 | 44.43–46.77 | 2.33 | Tight two-shot, baker and Zak | Baker: "Mm. Attention, je connais ta mère, hein." | reframes in the first 0.5 s | Baker raises a finger |
| 20 | 46.77–49.40 | 2.63 | Medium single, Marlon at the door; ends chest up | Marlon: "Morning. Everything okay?" | near static; he walks to the lens | 1.1 s silent walk-in, then the line |
| 21 | 49.40–51.00 | 1.60 | Close-up curly woman, croissant racks; Zak's hand in front | Curly: "He's forty cents short for a baguette!" | static | Points down at the hand |
| 22 | 51.00–52.93 | 1.93 | Two-shot, Marlon and Zak | Marlon: "I got him." | static | Drops a coin in Zak's hand |
| 23 | 52.93–55.27 | 2.33 | Side two-shot across the counter | Baker: "Mm. Merci, Marlon. Zak, dis merci." | static | Hands over the baguette |
| 24 | 55.27–56.90 | 1.63 | Medium single, wavy woman | Wavy: "And us?! What do WE get?!" | static | Spreads her arms |
| 25 | 56.90–59.40 | 2.50 | Extreme close-up, baker | Baker: "Mm. Tomorrow. Call at six fifty-eight." | static | Raises a finger at the end |
| 26 | 59.40–61.03 | 1.63 | Close-up, curly woman | Curly: "Who calls a bakery at six fifty-eight?!" | static | Hands to her hair |
| 27 | 61.03–63.50 | 2.47 | Wide: baker in front, Zak leaving | Baker: "Mm. Zak. Ta mère a appelé. Rentre." | static | Zak walks out with the baguette |

Cuts: 26 hard cuts, no dissolves. Three very fast 2–3 frame snaps inside shots (17.43, 43.3, 49.63 s) are either trimmed frames or abrupt generated motion; I did not count them as cuts.

## 4. Captions

| | reference.mp4 | reference2.mp4 |
|---|---|---|
| Position | bottom centre, one line, text at 91–94% of frame height | bottom centre, one or two lines, 86.5–95% of height |
| Font | white semi-bold sans, thin dark outline/shadow, small (cap height ~2.2% of frame height) | bold Arial-style sans, yellow (about RGB 252,255,23), black outline, cap height ~2.7% |
| Words at once | the whole line: 1–7 words, mean 3.7 | the whole line: 3–16 words, mean 6.3 |
| Highlight | none | none in colour; stressed words in capitals (THIS, MINE, VERY, HIS MOTHER, WE) |
| Animation | none; pops on and off | none |
| Timing | on ~0.1 s before the voice, off 0.2–0.3 s after; can spill ≤0.17 s over a cut | loosely timed; in the last third it leads the picture cut by 0.25–0.33 s |
| Total | 15 lines, 56 words | 27 lines, 169 words, mixed English and French |

## 5. Sound

- **reference.mp4**
  - There is a continuous low bed under the whole film, only about 7 dB below the dialogue, and never silent (the quietest second is about −27 dBFS).
  - Its bass moves between roughly 55, 49, 43/87 and 73 Hz, which suggests a slow music loop rather than room tone.
  - The bed is independent of the cuts.
  - Voice-band sound fills 33–39% of the time, including effort grunts at 5.9, 10.3, 10.8 and 16.1 s.
  - The first sound comes a median 0.31 s after a cut and the last ends 0.31 s before the next.
- **reference2.mp4**
  - A looping bass bed (period about 4.5 s) runs from ~5.0 to 14.8 s and from 18.0 to 58.8 s, and is absent at the start, in that hole and over the last two shots.
  - The bed does not follow the cuts, so it is a separate layer with deliberate drop-outs.
  - Between words in shot 27 the level falls to digital silence, so the voices are a clean track with no room tone.
  - Voice fills 53–64% of the time.
  - The first sound comes a median 0.22 s after a cut and the tail is 0.11 s; several lines start under the previous picture.
- I found no reliable evidence of isolated sound effects in either file.

## 6. Look, for image prompts

**Shared character rendering**
- Semi-realistic 2000s console cutscene models (fighting-game or Yakuza style): adult proportions, broad shoulders, slightly oversized hands with blocky fingers.
- Skin is matte with painted detail (pores, freckles, brow strokes, lip texture) on smooth, fairly low-poly faces; no subsurface glow.
- Eyes are large and clear with strong catchlights and painted lashes.
- Hair is chunky low-poly cards with visible flat facets and a jagged silhouette.
- Clothes are stiff, with baked wrinkles and high-contrast fabric textures (denim noise, velour sheen); no cloth simulation.

**Zak (appears in both)**
- Slicked-back silver hair with green streaks, tan skin, sharp jaw.
- One green eye and one purple eye; a scar through one eyebrow.
- Emerald zip tracksuit with a two-dot logo (mint and lilac).
- Black headphones with neon-green rings round the neck; black crossbody bag.

**reference.mp4: gym at night**
- Set: top-floor gym with floor-to-ceiling windows onto a city panorama and a lit pale-yellow basilica on a hill; dumbbell racks, a bench press with comically oversized black plates, grey mullions, ceiling light panels.
- Lighting: flat, even overhead light, soft frontal fill on faces, almost no cast shadows.
- Colour: deep navy background with warm city lights; emerald, denim blue and orange hair pop against it; medium contrast, no grain.
- Lens: normal to short tele for the close shots, wide for the low-angle point; everything in focus; no motion blur.
- Era defects: aliased hair and bar edges, low-resolution backdrop image, glow on the basilica, simple hands, props clipping.

**reference2.mp4: bakery by day**
- Set: Parisian bakery with a wooden counter and glass case, baguette baskets, bread shelves, chalkboards with bread drawings, curtained windows onto a street.
- Lighting and colour: warm golden light, cream, caramel and wood tones, blown-out hazy windows.
- Lens: blurred backgrounds behind the close-ups, more than a real console would show.
- Women: glossy full lips, heavy lashes, big eyes.
- Baker: long angular face, black slicked hair with a loose strand.

## 7. Overall numbers

| | reference.mp4 | reference2.mp4 |
|---|---|---|
| Shots | 13 | 27 |
| Mean / median / min / max length (s) | 2.74 / 3.04 / 1.21 / 3.92 | 2.35 / 2.13 / 1.30 / 5.83 |
| Shots ≤2 s / 2–3 s / 3–4 s / >4 s | 4 / 2 / 7 / 0 | 11 / 13 / 1 / 2 |
| Any shot >8 s or >10 s | none | none |
| Close-ups (incl. extreme) | 3 (23%) | 11 (41%; 3 with a listener visible) |
| Medium singles | 3 (23%) | 4 (15%) |
| Two-shots | 2 (15%; one is reached by a pan) | 7 (26%) |
| Over-the-shoulder | 2 (15%) | 3 (11%) |
| Wide | 3 (23%) | 2 (7%) |
| Separate insert shots | 0 | 0 (props are handled inside shots) |
| Shots with two or more main characters | 6 of 13 (55% of the time) | 15 of 27 (57% of the time) |
| Longest continuous line | 2.35 s ("Haychik frérot… aide-moi !", face hidden) | 16 words, about 4.8 s with pauses (shot 2) |
| Locked camera | 11 of 13 | 13 of 27; the rest drift slowly or push in; no handheld shake |
| Shots opening on a clean posed still | 9 of 13 (animation holds) | 20 of 27 (74%); the other 7 open mid-motion |
| Distinct camera set-ups | 12 | about 19 start images |

## 8. Recipe

**Smallest set of start images for a two-character sketch of 35–45 s (14–17 clips)**

1. **Master two-shot:** both characters chest up in the set. Used for the opening line and any exchange.
2. **Single of the calm character:** frontal, chest up, neutral, mouth closed. Reused for all the deadpan replies.
3. **Close-up of the excitable character:** frontal. Reused for the indignant lines.
4. **Over-the-shoulder:** one character seen past the other's shoulder. Keeps the geography and shows the listener.
5. **Wide gag angle:** both full figure, for the physical joke; reusable before and after the gag.
6. **Extreme close-up of the calm character:** for the punchline.
7. **Optional:** the thing they are talking about (prop or third party), seen over their shoulders.
8. **Optional:** a medium shot for a cameo entrance.

**What each generated clip must contain**

- **One line only.** Typically 3–7 words; 16 at most.
- **Request 5–6 s and trim.** Final shots run 1.2–3.9 s, with at most one of 4.5–6 s.
- **Clean start.** Open on the posed still, mouth closed, with 0.2–0.3 s before the first syllable.
- **Clean end.** Hold the expression for 0.3–0.8 s after the last word, so no cut lands inside a word.
- **One acting beat.** One gesture or one expression change; hands otherwise parked or busy with a prop.
- **A still listener.** Whoever is not speaking does not move.
- **Locked camera.** Allow only the slow push-in on the punchline and at most one eased pan.
- **Clean picture.** No on-screen text, no music, 4:3 at 576 lines, 24 fps.

**In the edit**

- Do not use the same framing on the same character twice in a row.
- Add the music bed and the full-line bottom-centre captions afterwards.
- Leave silent beats of 1.0–1.4 s before the answer and before the punchline, as reference.mp4 does.

## 9. Work files

Everything is in `/tmp/claude-0/-home-user-mindcare/a7878755-9e4c-5740-b306-7f25e8d8722e/scratchpad/study/work/recipe`:

- `r1/sheet_01.jpg`–`sheet_04.jpg` and `r2/sheet_01.jpg`–`sheet_07.jpg`: contact sheets at 2 frames per second.
- `r1/keys/` and `r2/keys/`: first, +0.5 s, middle and last frame of every shot.
- `r1/native_a.jpg`, `r1/native_b.jpg`, `r2/native_a.jpg`, `r2/native_b.jpg`: frames at native resolution.
- `r2/firsts_curly.jpg`, `r2/firsts_baker.jpg`: first frames of shots that share a set-up.
- `cap_zoom.jpg`: both caption styles enlarged.
- Scripts: `diffs.py`, `shots.py`, `cam.py`, `caps.py`, `audio.py`, `audiocuts.py`, `bed.py`, `bed2.py`, `pershot.py`, `keys.py`, `firsts.py`, `strip.sh`.
- Data: `r1/scene.txt`, `r2/scene.txt` (and `scene_all.txt`), `r1/d.npy`, `r2/d.npy`, `r1/audio_env.npz`, `r2/audio_env.npz`.