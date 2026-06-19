import pystray
from PIL import Image, ImageDraw
import threading

class TrayManager:
    def __init__(self, on_exit_callback):
        self.is_tracking_active = True
        self.on_exit_callback = on_exit_callback
        self.icon = None

    def create_icon_image(self):
        # สร้างรูปไอคอนขนาด 64x64 แบบง่ายๆ (วงกลมสีฟ้า) สำหรับแสดงใน System Tray
        image = Image.new('RGB', (64, 64), color='black')
        dc = ImageDraw.Draw(image)
        dc.ellipse((16, 16, 48, 48), fill='cyan')
        return image

    def toggle_tracking(self, icon, item):
        self.is_tracking_active = not self.is_tracking_active
        # อัปเดตข้อความในเมนู
        item.text = "⏸️ Pause" if self.is_tracking_active else "▶️ Resume"
        print(self.is_tracking_active)

    def quit_app(self, icon, item):
        print("Shutting down Application...")
        icon.stop() # ปิดไอคอนใน Tray
        self.on_exit_callback() # เรียกฟังก์ชันปิดกล้องใน main.py

    def run(self):
        # สร้างเมนูคลิกขวา
        menu = pystray.Menu(
            pystray.MenuItem("▶️ Resume", self.toggle_tracking, checked=lambda item: self.is_tracking_active),
            pystray.MenuItem("❌ Exit", self.quit_app)
        )
        
        self.icon = pystray.Icon("HandController", self.create_icon_image(), "Hand Gesture Controller", menu)
        
        # รัน System Tray แยกออกเป็นอีก Thread เพื่อไม่ให้บล็อกการทำงานหลัก
        threading.Thread(target=self.icon.run, daemon=True).start()