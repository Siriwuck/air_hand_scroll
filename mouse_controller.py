import config
import time
from evdev import UInput, ecodes as e

class MouseController:
    def __init__(self):
        cap = {
            # เพิ่ม e.REL_HWHEEL เข้าไปในบอร์ดจำลองอุปกรณ์ REL_X, REL_Y, REL_WHEEL
            e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL, e.REL_HWHEEL], 
            e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE]
        }
        try:
            self.ui = UInput(cap, name='AI-Virtual-Hardware-Mouse')
            print("[Hardware Emulation] Virtual Mouse registered successfully.")
        except Exception as err:
            print(f"Error initializing uinput: {err}")
            raise err
        
        self.prev_smooth_x, self.prev_smooth_y = None, None
        self.smoothing = 8.0      
        self.sensitivity = 1.8    
        self.is_dragging = False

    # --- ปรับปรุงฟังก์ชัน Scroll ให้รองรับทั้งแนวตั้งและแนวนอน ---
    def scroll_mouse(self, v_speed, h_speed=0):
        # v_speed: แกน Y (เป็นบวก = เลื่อนขึ้น, เป็นลบ = เลื่อนลง)
        # h_speed: แกน X (เป็นบวก = เลื่อนขวา, เป็นลบ = เลื่อนซ้าย)
        if v_speed != 0:
            self.ui.write(e.EV_REL, e.REL_WHEEL, v_speed)
        if h_speed != 0:
            self.ui.write(e.EV_REL, e.REL_HWHEEL, h_speed)
        
        if v_speed != 0 or h_speed != 0:
            self.ui.syn()

    # --- ฟังก์ชันอื่นๆ คอมเมนต์เก็บไว้เหมือนเดิม ---
    def move_mouse(self, index_x, index_y):
        if self.prev_smooth_x is None or self.prev_smooth_y is None:
            self.prev_smooth_x, self.prev_smooth_y = index_x, index_y
            return
        next_smooth_x = self.prev_smooth_x + (index_x - self.prev_smooth_x) / self.smoothing
        next_smooth_y = self.prev_smooth_y + (index_y - self.prev_smooth_y) / self.smoothing
        dx = int((next_smooth_x - self.prev_smooth_x) * self.sensitivity)
        dy = int((next_smooth_y - self.prev_smooth_y) * self.sensitivity)
        if dx != 0 or dy != 0:
            self.ui.write(e.EV_REL, e.REL_X, dx)
            self.ui.write(e.EV_REL, e.REL_Y, dy)
            self.ui.syn()
        self.prev_smooth_x, self.prev_smooth_y = next_smooth_x, next_smooth_y

    def reset_origin(self):
        self.prev_smooth_x, self.prev_smooth_y = None, None

    def drag_start(self):
        if not self.is_dragging:
            self.ui.write(e.EV_KEY, e.BTN_LEFT, 1)
            self.ui.syn()
            self.is_dragging = True

    def drag_end(self):
        if self.is_dragging:
            self.ui.write(e.EV_KEY, e.BTN_LEFT, 0)
            self.ui.syn()
            self.is_dragging = False

    def left_click(self):
        self.drag_end()
        self.ui.write(e.EV_KEY, e.BTN_LEFT, 1)
        self.ui.syn()
        time.sleep(0.05)
        self.ui.write(e.EV_KEY, e.BTN_LEFT, 0)
        self.ui.syn()