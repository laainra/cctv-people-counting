import cv2

cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
if not cap.isOpened():
    print("Gagal buka kamera eksternal.")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("Gagal baca frame.")
        break

    cv2.imshow("Kamera Logitech C270", frame)

    if cv2.waitKey(1) == 27:  # ESC buat keluar
        break

cap.release()
cv2.destroyAllWindows()
