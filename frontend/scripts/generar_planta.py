"""Genera las variantes de Cebollita segun el estado que estima el modelo.

A partir de src/assets/cebollita.png (la ilustracion original) deforma las hojas
y cambia el color para obtener las cuatro versiones que usa la pagina:

    bien, luz, agua, mal  ->  src/assets/plant/<estado>.webp

Uso (necesita pillow, numpy y opencv-python-headless):
    python scripts/generar_planta.py
"""

from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "assets" / "cebollita.png"
OUT = ROOT / "src" / "assets" / "plant"

POT_TOP = 750  # fila donde empieza la maceta
CENTER_X = 540  # eje de la planta
OUT_WIDTH = 720
# Se recorta el espacio vacio: la base de la maceta queda justo en el borde de abajo
# (asi la sombra del suelo se apoya ahi). Se agrega margen a los costados para las hojas caidas.
# Relacion final: 1200 x 984 (la usa el CSS de .plantstage__stage).
CROP_TOP, CROP_BOTTOM, PAD_X = 140, 1124, 60


def warp_leaves(img, scale_y=1.0, scale_x=1.0, sag=0.0, lean=0.0):
    """Deforma solo la parte de arriba (hojas) y la pega sobre la maceta original.

    scale_y < 1 aplasta las hojas, `sag` hace caer las puntas laterales (en px)
    y `lean` inclina la copa hacia un lado (en px en lo mas alto).
    """
    h, w = img.shape[:2]
    u, v = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

    out_height = POT_TOP - v  # altura sobre la maceta en la imagen de salida
    side = np.abs(u - CENTER_X) / CENTER_X
    pushed = sag * side**1.6  # cuanto baja ese punto por el peso de la hoja
    src_height = (out_height + pushed) / scale_y
    src_y = POT_TOP - src_height
    lean_shift = lean * np.clip(src_height / (POT_TOP - 200), 0, 1) ** 1.5
    src_x = CENTER_X + (u - CENTER_X - lean_shift) / scale_x

    leaves = cv2.remap(
        img, src_x, src_y, cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
    )
    leaves[src_height <= 0] = 0  # solo hojas (lo que estaba sobre la maceta)

    base = img.copy()
    base[:POT_TOP] = 0  # maceta (y hojas que cuelgan delante) sin tocar
    # Las hojas caidas quedan por delante de la maceta.
    return alpha_over(leaves, base)


def alpha_over(top, bottom):
    """Compone `top` sobre `bottom` (ambos BGRA uint8)."""
    ta = top[..., 3:4].astype(np.float32) / 255
    ba = bottom[..., 3:4].astype(np.float32) / 255
    out_a = ta + ba * (1 - ta)
    rgb = (top[..., :3] * ta + bottom[..., :3] * ba * (1 - ta)) / np.maximum(out_a, 1e-6)
    return np.dstack([rgb, out_a * 255]).clip(0, 255).astype(np.uint8)


def leaf_mask(img):
    """Mascara suave de las hojas (verde + manchas blancas), sin la maceta."""
    hsv = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2HSV)
    green = ((hsv[..., 0] > 28) & (hsv[..., 0] < 90) & (hsv[..., 1] > 55)).astype(np.uint8) * 255
    closed = cv2.morphologyEx(green, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    # Debajo del borde de la maceta el esmalte tambien es verdoso: solo el verde intenso.
    strong = ((hsv[..., 0] > 35) & (hsv[..., 0] < 85) & (hsv[..., 1] > 105)).astype(np.uint8) * 255
    closed[POT_TOP - 10:] = strong[POT_TOP - 10:]
    mask = cv2.GaussianBlur(closed, (0, 0), 3).astype(np.float32) / 255
    return mask * (img[..., 3] > 10)


def tint(img, hue_shift=0.0, sat=1.0, val=1.0, brown=0.0, seed=1):
    """Cambia el color solo de las hojas. `brown` agrega manchas secas."""
    mask = leaf_mask(img)
    hsv = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 0] += hue_shift
    hsv[..., 1] *= sat
    hsv[..., 2] *= val
    if brown > 0:
        rng = np.random.default_rng(seed)
        noise = cv2.GaussianBlur(rng.random(img.shape[:2]).astype(np.float32), (0, 0), 14)
        noise = (noise - noise.min()) / (noise.max() - noise.min())
        # Puntas y bordes se secan primero: mas marron lejos del centro y arriba.
        yy, xx = np.mgrid[: img.shape[0], : img.shape[1]]
        edge = np.clip(np.abs(xx - CENTER_X) / CENTER_X * 0.7 + (POT_TOP - yy) / 600 * 0.3, 0, 1)
        dry = np.clip((noise * 1.1 + edge * 0.5 - 0.55) * 3, 0, 1) * brown
        hsv[..., 0] = hsv[..., 0] * (1 - dry) + 16 * dry  # hacia marron
        hsv[..., 1] = hsv[..., 1] * (1 - dry) + 120 * dry
        hsv[..., 2] = hsv[..., 2] * (1 - 0.35 * dry)
    hsv[..., 0] = np.clip(hsv[..., 0], 0, 179)
    hsv[..., 1:] = np.clip(hsv[..., 1:], 0, 255)
    rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    out = img.copy()
    m = mask[..., None]
    out[..., :3] = (rgb * m + img[..., :3] * (1 - m)).astype(np.uint8)
    return out


def save(img, name):
    img = cv2.copyMakeBorder(img[CROP_TOP:CROP_BOTTOM], 0, 0, PAD_X, PAD_X, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
    h, w = img.shape[:2]
    small = cv2.resize(img, (OUT_WIDTH, round(h * OUT_WIDTH / w)), interpolation=cv2.INTER_AREA)
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / f"{name}.webp"), small, [cv2.IMWRITE_WEBP_QUALITY, 88])
    print("ok", name)


def main():
    img = cv2.imread(str(SRC), cv2.IMREAD_UNCHANGED)

    # Estoy bien: la ilustracion original, con un poco mas de vida.
    save(tint(img, sat=1.08, val=1.03), "bien")

    # Preciso luz: hojas palidas y amarillentas, copa estirada e inclinada hacia la luz.
    pale = tint(img, hue_shift=-6, sat=0.62, val=1.1)
    save(warp_leaves(pale, scale_y=1.1, scale_x=0.97, sag=0, lean=55), "luz")

    # Preciso agua: hojas caidas y apagadas.
    dull = tint(img, hue_shift=-4, sat=0.82, val=0.93, brown=0.25, seed=3)
    save(warp_leaves(dull, scale_y=0.8, scale_x=1.05, sag=210), "agua")

    # Estoy mal: muy caida, grisacea y con hojas secas.
    sick = tint(img, hue_shift=-8, sat=0.5, val=0.8, brown=0.85, seed=7)
    save(warp_leaves(sick, scale_y=0.68, scale_x=1.08, sag=300), "mal")


if __name__ == "__main__":
    main()
