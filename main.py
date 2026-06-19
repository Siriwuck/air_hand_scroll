import cv2
import math
import time
import sys
from hand_tracker import HandTracker
from mouse_controller import MouseController
import config

def main():
    # โหลดไดรเวอร์เข้า Kernel ก่อนรัน
    import os
    os.system("sudo modprobe uinput")

    cap = cv2.VideoCapture(0)
    
    # --- บังคับตั้งค่าความละเอียดต่ำเพื่อรีดความเร็ว FPS ---
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    # ---------------------------------------------------
    
    tracker = HandTracker()
    
    try:
        mouse = MouseController()
    except Exception:
        print("Failed to initialize Virtual Mouse. Make sure you run with 'sudo'.")
        sys.exit(1)

    last_double_click_time = 0
    last_right_click_time = 0
    last_left_click_time = 0
    click_cooldown = 1.0
    # ====================================================
    # ⚙️ ตั้งค่าตัวแปรระบบแบ่งโซน Air Scroll (วางก่อนเข้าลูป while True)
    # ====================================================
    is_scroll_mode = False       # เริ่มต้นโปรแกรม โหมดนี้จะปิด (OFF) เสมอ
    trigger_held = False         # ตัวล็อกป้องกันโหมดเปิด/ปิดรัวๆ ตอนแช่นิ้วชนกัน

    # สมมติหน้าต่างกล้องสูง 480 พิกเซล (แบ่ง 3 ส่วน ส่วนละ 160 พิกเซล)
    ZONE_UP_BOUNDARY = 100        # น้อยกว่านี้ = โซนบน (Scroll Up)
    ZONE_DOWN_BOUNDARY = 200      # มากกว่านี้ = โซนล่าง (Scroll Down)
    # ช่วงระหว่าง 160 - 320 จะเป็นโซนกลาง (Neutral / หยุดนิ่งกึก)

    scroll_interval = 0.08        # ความเร็วในการไหลของจอ (วินาที/สเตป) ยิ่งน้อยยิ่งไว
    last_scroll_time = 0

    print("=======================================================")
    print(" 🚀 Wayland-Native Hand Gesture Controller Active")
    print("=======================================================")
    print(" 🟢 Status: RUNNING (Control via Linux Kernel Device)")
    print(" ⌨️  Press 'Ctrl + C' in this terminal to Exit safely")
    print("=======================================================")

    try:
        while True:
            success, img = cap.read()
            if not success:
                time.sleep(0.1)
                continue
                
            img = cv2.flip(img, 1)
            lmList, img = tracker.get_landmarks(img)

            if len(lmList) != 0:
                # 1. ดึงพิกัดนิ้วที่ต้องใช้
                x_idx, y_idx = lmList[8][1], lmList[8][2]         # จุดที่ 8: นิ้วชี้ (ใช้คุมโซน Scroll)
                x_thumb, y_thumb = lmList[4][1], lmList[4][2]     # จุดที่ 4: นิ้วโป้ง (ใช้ร่วมทำ Trigger)
                x_pinky, y_pinky = lmList[20][1], lmList[20][2]   # จุดที่ 20: นิ้วก้อย (ใช้ร่วมทำ Trigger)

                # ====================================================
                # 🟢 สเตปที่ 1: สวิตช์ Toggle (นิ้วก้อย + นิ้วโป้ง แตะกันเพื่อเปิด/ปิด)
                # ====================================================
                dist_trigger = math.hypot(x_pinky - x_thumb, y_pinky - y_thumb)
                
                # ตั้งระยะไว้ที่ 35 พิกเซล ให้สะบัดนิ้วมาชนกันได้ง่ายๆ ไม่ต้องออกแรงบีบ
                if dist_trigger < 15: 
                    if not trigger_held:
                        is_scroll_mode = not is_scroll_mode  # สลับสถานะ ON/OFF
                        trigger_held = True                  # ล็อกคำสั่งไว้
                        # if is_scroll_mode:
                        #     # print("Zone Scroll Mode: ON 🟢 (Pinky + Thumb Activated)")
                        # else:
                        #     # print("Zone Scroll Mode: OFF 🔴")
                else:
                    trigger_held = False  # ปลดล็อกเมื่อแยกนิ้วออกจากกัน

                # ====================================================
                # 🟢 สเตปที่ 2: ระบบควบคุมการไหลตามโซน (โฟกัสที่แกน Y ของนิ้วชี้)
                # ====================================================
                if is_scroll_mode:
                    current_time = time.time()

                    # 🔼 โซนที่ 1 (โซนบน): นิ้วชี้ลอยอยู่ขอบบนของจอ -> สกรอลล์ขึ้นเรื่อยๆ
                    if y_idx < ZONE_UP_BOUNDARY:
                        if current_time - last_scroll_time > scroll_interval:
                            mouse.scroll_mouse(1)  
                            last_scroll_time = current_time
                            # print("Scrolling UP ↑")

                    # 🔽 โซนที่ 3 (โซนล่าง): นิ้วชี้กดลงมาขอบล่างของจอ -> สกรอลล์ลงเรื่อยๆ
                    elif y_idx > ZONE_DOWN_BOUNDARY:
                        if current_time - last_scroll_time > scroll_interval:
                            mouse.scroll_mouse(-1) 
                            last_scroll_time = current_time
                            # print("Scrolling DOWN ↓")

                    # ⏹️ โซนที่ 2 (โซนกลาง): นิ้วชี้พักอยู่ตรงกลาง -> หยุดนิ่งสนิททันที
                    else:
                        # ปล่อยผ่าน ไม่ส่งคำสั่งใดๆ หน้าจอจะหยุดกึกทันที สะบัดนิ้วเข้าโซนนี้เพื่อเบรกได้เลย
                        pass

            else:
                mouse.reset_origin()
                # เซฟตี้: ถ้ามือหลุดจากหน้ากล้อง ให้ปิดโหมดสกรอลล์ทันที
                if is_scroll_mode:
                    is_scroll_mode = False
                    # print("Hand lost. Zone Scroll Mode: OFF 🔴")

                # ====================================================
                # 🚫 [COMMENTED FOR FUTURE USE] ฟังก์ชันเมาส์และคลิกเดิม
                # ====================================================
                """
                dist_left   = math.hypot(x_thumb - x_idx, y_thumb - y_idx)     
                dist_right  = math.hypot(x_thumb - x_ring, y_thumb - y_ring)   
                dist_double = math.hypot(x_thumb - x_pinky, y_thumb - y_pinky) 
                current_time = time.time()

                if dist_double < 20 and (current_time - last_double_click_time > click_cooldown):
                    mouse.double_click()
                    last_double_click_time = current_time
                elif dist_right < 20 and (current_time - last_right_click_time > click_cooldown):
                    mouse.right_click()
                    last_right_click_time = current_time
                elif dist_left < 25 and (current_time - last_left_click_time > click_cooldown):
                    mouse.left_click()
                    last_left_click_time = current_time
                
                # ขยับลูกศรเมาส์ปกติ
                if scroll_start_y is None: # ถ้าไม่ได้สกรอลล์อยู่ค่อยให้เมาส์ขยับ
                    mouse.move_mouse(x_idx, y_idx)
                """


            # if len(lmList) != 0:
            #     x_idx, y_idx = lmList[8][1], lmList[8][2]       # นิ้วชี้
            #     x_mid, y_mid = lmList[12][1], lmList[12][2]     # นิ้วกลาง
            #     x_thumb, y_thumb = lmList[4][1], lmList[4][2]   # นิ้วโป้ง
            #     x_ring, y_ring = lmList[16][1], lmList[16][2]   # นิ้วนาง
            #     x_pinky, y_pinky = lmList[20][1], lmList[20][2] # นิ้วก้อย

            #     # คำนวณระยะห่าง
            #     dist_left   = math.hypot(x_thumb - x_idx, y_thumb - y_idx)     # ชี้ + โป้ง = Left Click
            #     dist_drag   = math.hypot(x_thumb - x_mid, y_thumb - y_mid)     # กลาง + โป้ง = Trigger Drag
            #     dist_right  = math.hypot(x_thumb - x_ring, y_thumb - y_ring)   # นาง + โป้ง = Right Click
            #     dist_double = math.hypot(x_thumb - x_pinky, y_thumb - y_pinky) # ก้อย + โป้ง = Double Click

            #     current_time = time.time()

            #     # 🟢 สเตปที่ 1: ระบบสวิตช์เปิด/ปิด Drag (Toggle Mode)
            #     if dist_drag < 25:
            #         if not drag_hand_closed:
            #             dragging_state = not dragging_state # สลับสถานะ (ถ้าลากอยู่จะหยุด ถ้าหยุดอยู่จะลาก)
            #             if dragging_state:
            #                 mouse.drag_start()
            #             else:
            #                 mouse.drag_end()
            #             drag_hand_closed = True # ล็อกไว้จนกว่าจะปล่อยนิ้วแยกจากกันก่อน
            #     else:
            #         drag_hand_closed = False # ปลดล็อกเมื่อนิ้วแยกจากกันแล้ว พร้อมสำหรับการแตะครั้งต่อไป

            #     # 🟢 สเตปที่ 2: แยกการทำงานตามสถานะ (State-based Actions)
            #     if not dragging_state:
            #         # >>> โหมดปกติ (ไม่ได้ลากไฟล์) <<< สามารถสั่งคลิกต่างๆ ได้ตามปกติ
            #         if dist_double < 20 and (current_time - last_double_click_time > click_cooldown):
            #             mouse.double_click()
            #             last_double_click_time = current_time

            #         elif dist_right < 20 and (current_time - last_right_click_time > click_cooldown):
            #             mouse.right_click()
            #             last_right_click_time = current_time

            #         elif dist_left < 25 and (current_time - last_left_click_time > click_cooldown):
            #             mouse.left_click()
            #             last_left_click_time = current_time

            #         # ขยับเมาส์ตามปกติ
            #         mouse.move_mouse(x_idx, y_idx)

            #     else:
            #         # >>> โหมดกำลังลากไฟล์ (Dragging Mode) <<<
            #         # ในโหมดนี้ต่อให้นิ้วแยกออกจากกันแล้ว ระบบก็จะไม่หลุดลาก 
            #         # เมาส์จะลากไฟล์ตามนิ้วชี้ไปเรื่อยๆ จนกว่าจะเอานิ้วกลางมาแตะนิ้วโป้งอีกครั้ง
            #         mouse.move_mouse(x_idx, y_idx)

            # else:
            #     mouse.reset_origin()

            # cv2.waitKey(1)

    except KeyboardInterrupt:
        print("\n[Shutting Down] Ctrl+C detected.")
    finally:
        print("Cleaning up camera resources...")
        cap.release()
        cv2.destroyAllWindows()
        print("Application terminated successfully.")

if __name__ == "__main__":
    main()