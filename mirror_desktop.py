import cv2
import numpy as np
import pyautogui

# Set the resolution (or capture a specific region of your screen)
# Here, we're taking the primary monitor's dimensions
screen_size = pyautogui.size()

# Optional: Adjust window name and set it to stay on top
window_name = "Desktop Mirror"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

print("Starting mirror... Press 'q' to stop.")

while True:
    # Capture the screen
    screenshot = pyautogui.screenshot()
    
    # Convert the screenshot to a NumPy array
    frame = np.array(screenshot)
    
    # Convert from RGB to BGR (OpenCV's default color format)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
    # Display the mirrored frame
    cv2.imshow(window_name, frame)
    
    # Break the loop if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# cv2.destroyAllWindows()
