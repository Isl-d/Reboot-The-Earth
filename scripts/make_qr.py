"""QR code for the cooler box: scanning it opens TRK-07's freshness passport.

    python scripts/make_qr.py                      # http://<this laptop>:8000/track/TRK-07
    python scripts/make_qr.py --host 192.168.1.50  # pin the address for the demo network

Print it and tape it to the lid. Judges scan it with their own phones, which is
the point: the freshness record belongs to the box, not to our laptop screen.
"""
from __future__ import annotations

import argparse
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def local_ip() -> str:
    """The address this laptop has on the demo network, not 127.0.0.1."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))          # no packet is sent; this just picks a route
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=None, help="laptop IP on the demo network")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--truck", default="TRK-07")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    host = args.host or local_ip()
    url = f"http://{host}:{args.port}/track/{args.truck}"
    out = Path(args.out) if args.out else ROOT / "qr" / f"{args.truck}.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        import qrcode
    except ImportError:
        raise SystemExit("pip install 'qrcode[pil]' first, then run this again")

    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(out)

    print(f"{url}\n-> {out}")
    print("Check it with your own phone on the demo Wi-Fi before printing.")


if __name__ == "__main__":
    main()
