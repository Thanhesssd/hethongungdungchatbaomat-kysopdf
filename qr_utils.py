import qrcode
import json
import cv2
from PIL import Image
from pyzbar.pyzbar import decode

class QRManager:
    @staticmethod
    def generate_contact_qr(ip_address, port, public_key_pem):
        data = {
            "ip": ip_address,
            "port": port,
            "public_key": public_key_pem,
            "fingerprint": ""
        }
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(json.dumps(data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img

    @staticmethod
    def decode_qr_image(image_path):
        try:
            img = Image.open(image_path)
            decoded = decode(img)
            if not decoded:
                return None
            qr_data = decoded[0].data.decode("utf-8")
            return json.loads(qr_data)
        except Exception as e:
            print(f"Lỗi giải mã QR: {e}")
            return None

    @staticmethod
    def decode_qr_from_camera():
        cap = cv2.VideoCapture(0)
        result = None
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            decoded = decode(frame)
            for d in decoded:
                try:
                    result = json.loads(d.data.decode("utf-8"))
                    cap.release()
                    cv2.destroyAllWindows()
                    return result
                except Exception:
                    pass
            cv2.imshow("Quét QR – Nhấn Q để thoát", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        cap.release()
        cv2.destroyAllWindows()
        return result