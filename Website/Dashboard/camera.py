# camera.py
import cv2
import threading

class VideoCamera:
    def __init__(self):
        self.video = cv2.VideoCapture(1, cv2.CAP_DSHOW)
        (self.grabbed, self.frame) = self.video.read()
        self.lock = threading.Lock()
        self.running = True

        # Thread untuk update frame
        thread = threading.Thread(target=self.update_frame, args=())
        thread.daemon = True
        thread.start()

    def update_frame(self):
        while self.running:
            grabbed, frame = self.video.read()
            with self.lock:
                self.grabbed = grabbed
                self.frame = frame

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.running = False
        self.video.release()

camera_instance = VideoCamera()
