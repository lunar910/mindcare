"""Face landmarks (478 points, MediaPipe Face Landmarker) on a picture.   python landmarks.py IN.png OUT.json [preview.png]

Run with the mpenv interpreter (mediapipe lives there).  Points are returned in pixels (x, y) of the input picture."""
import json, sys
import numpy as np
import mediapipe as mp
from PIL import Image, ImageDraw
MODEL = '/tmp/claude-0/-home-user-mindcare/a7878755-9e4c-5740-b306-7f25e8d8722e/scratchpad/models_dl/face_landmarker.task'


def detect(path):
    im = Image.open(path).convert('RGBA')
    bg = Image.new('RGBA', im.size, (120, 120, 126, 255))
    bg.alpha_composite(im)
    rgb = np.ascontiguousarray(np.asarray(bg.convert('RGB')))
    opts = mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=MODEL), num_faces=1,
                                                 min_face_detection_confidence=0.2, min_face_presence_confidence=0.2)
    with mp.tasks.vision.FaceLandmarker.create_from_options(opts) as fl:
        res = fl.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not res.face_landmarks:
        return None, rgb
    h, w = rgb.shape[:2]
    return np.array([(p.x * w, p.y * h, p.z * w) for p in res.face_landmarks[0]]), rgb


if __name__ == '__main__':
    pts, rgb = detect(sys.argv[1])
    if pts is None:
        print('no face found'); sys.exit(2)
    json.dump(pts.tolist(), open(sys.argv[2], 'w'))
    print('landmarks', len(pts))
    if len(sys.argv) > 3:
        im = Image.fromarray(rgb); d = ImageDraw.Draw(im)
        for x, y, z in pts:
            d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=(0, 255, 0))
        for i in (33, 133, 362, 263, 61, 291, 13, 14, 152, 70, 105, 107, 336, 334, 300, 468, 473, 1):
            x, y, _ = pts[i]; d.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(255, 0, 0), width=2)
        im.save(sys.argv[3])
