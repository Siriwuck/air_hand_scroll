import cv2
import math
import time
import sys
import os
from hand_tracker import HandTracker
from mouse_controller import MouseController
import config

def main():
    print("Loading uinput kernel module...")
    os.system("sudo modprobe uinput")

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("❌ Cannot open camera index 0. Exiting.")
        os._exit(1)

    tracker = HandTracker()
    
    try:
        mouse = MouseController()
    except Exception:
        print("Failed to initialize Virtual Mouse. Make sure you run with 'sudo'.")
        sys.exit(1)

    is_scroll_mode = False       
    trigger_held = False         

    # ====================================================
    # ⚙️ [ADJUSTED] ปรับโซนแกน Y ใหม่ให้ควบคุมง่ายขึ้น ไม่ต้องเอื้อมมือสูง
    # ====================================================
    ZONE_UP_BOUNDARY = 80        # นิ้วชี้อยู่ครึ่งบนของจอ = Scroll Up
    ZONE_DOWN_BOUNDARY = 140      # นิ้วชี้อยู่ครึ่งล่างของจอ = Scroll Down
    scroll_interval = 0.04        # ปรับให้ไหลลื่นขึ้นนิดหน่อย
    last_scroll_time = 0

    try:
        while True:        
            success, img = cap.read()
            if not success:
                cv2.waitKey(1)
                continue
                
            img = cv2.flip(img, 1)
            lmList, img = tracker.get_landmarks(img)

            if len(lmList) != 0:
                x_idx, y_idx = lmList[8][1], lmList[8][2]         
                x_thumb, y_thumb = lmList[4][1], lmList[4][2]     
                x_pinky, y_pinky = lmList[20][1], lmList[20][2]   
                x_ring, y_ring = lmList[16][1], lmList[16][2]     

                dist_break = math.hypot(x_ring - x_thumb, y_ring - y_thumb) 
                dist_trigger = math.hypot(x_pinky - x_thumb, y_pinky - y_thumb)
                
                # ====================================================
                # 🛑 [ADJUSTED] เพิ่มระยะ Threshold เป็น 40 ป้องกันนิ้วลั่นควบรวมกัน
                # ====================================================
                if dist_break < 10: 
                    print("\n>>> 🛑 Ring + Thumb Detected! Exiting program instantly...")
                    break 

                elif dist_trigger < 10: 
                    if not trigger_held:
                        is_scroll_mode = not is_scroll_mode  
                        trigger_held = True                  
                        print(f">>> 🟢 Scroll Mode is now: {'ON' if is_scroll_mode else 'OFF'}")
                else:
                    trigger_held = False 

                # ====================================================
                # 🔄 ระบบเลื่อนหน้าจอตามโซนแกน Y ของนิ้วชี้
                # ====================================================
                if is_scroll_mode:
                    current_time = time.time()
                    if y_idx < ZONE_UP_BOUNDARY:
                        if current_time - last_scroll_time > scroll_interval:
                            mouse.scroll_mouse(1)  
                            last_scroll_time = current_time
                            # print("    ⬆️ [ACTION] Scrolling UP")
                            
                    elif y_idx > ZONE_DOWN_BOUNDARY:
                        if current_time - last_scroll_time > scroll_interval:
                            mouse.scroll_mouse(-1) 
                            last_scroll_time = current_time
                            # print("    ⬇️ [ACTION] Scrolling DOWN")
            else:
                mouse.reset_origin()
                # if is_scroll_mode:
                #     is_scroll_mode = False

            if cv2.waitKey(1) & 0xFF == 27:
                break

    except KeyboardInterrupt:
        pass

    print("Releasing camera and killing python process...")
    cap.release()
    cv2.destroyAllWindows()
    os._exit(0)

if __name__ == "__main__":
    main()