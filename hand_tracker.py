import cv2
import mediapipe as mp

class HandTracker:
    def __init__(self):
        self.mpHands = mp.solutions.hands
        # กำหนด max_num_hands=1 เพื่อให้จับมือเดียว ป้องกันเมาส์กระโดด
        self.hands = self.mpHands.Hands(max_num_hands=1, min_detection_confidence=0.7)
        self.mpDraw = mp.solutions.drawing_utils

    def get_landmarks(self, img):
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands.process(imgRGB)
        lmList = []
        
        if results.multi_hand_landmarks:
            myHand = results.multi_hand_landmarks[0]
            for id, lm in enumerate(myHand.landmark):
                h, w, c = img.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                lmList.append([id, cx, cy])
            
            # วาดเส้นโครงสร้างมือบนภาพ
            self.mpDraw.draw_landmarks(img, myHand, self.mpHands.HAND_CONNECTIONS)
            
        return lmList, img