"""
Raspberry Pi Photobooth

Main application for the Raspberry Pi 4 Model B.

Originally developed as an undergraduate Embedded Systems laboratory exercise.
Archived for reference and educational purposes.

Copyright (c) 2026
Sean Patrick Razo
Samuel Roy Malleta
Jaymar Poñegal

SPDX-License-Identifier: MIT
"""

#Import the necessary Packages for this software to run
import mediapipe
import cv2
from collections import Counter
import time
import threading
from PIL import Image
import RPi.GPIO as GPIO
from pathlib import Path

# Project paths

BASE_DIR = Path(__file__).resolve().parent
FRAME_DIR = BASE_DIR / "assets" / "frames"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Import frame designs
plain_frame = Image.open(FRAME_DIR / "frame-1-plain.png")
forever_frame = Image.open(FRAME_DIR / "frame-2-forever.png")
blast_frame = Image.open(FRAME_DIR / "frame-3-blast.png")
glowing_frame = Image.open(FRAME_DIR / "frame-4-glowing.png")

# Initialize frame choosing variables
burst_img_counter = 1
chosen_frame = 1

# GPIO Initialization
# Disable warnings
GPIO.setwarnings(False)
# Select GPIO Mode
GPIO.setmode(GPIO.BCM)
# Set red, green, and blue pins
RED_LED_PIN = 12
GREEN_LED_PIN = 19
BLUE_LED_PIN = 13
# Set pins as outputs
GPIO.setup(RED_LED_PIN,GPIO.OUT)
GPIO.setup(GREEN_LED_PIN,GPIO.OUT)
GPIO.setup(BLUE_LED_PIN,GPIO.OUT)

# Use MediaPipe to draw the hand framework over the top of hands it identifies in Real-Time
drawingModule = mediapipe.solutions.drawing_utils
handsModule = mediapipe.solutions.hands

# Initialize the primary camera stream.
cap = cv2.VideoCapture(0)
finger_tip_landmarks=[8,12,16,20]
fingers=[]
finger=[]

# Set frame size & FPS
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
DESIRED_FPS = 30

# Function to turn RGB LED to white
def led_white():
    GPIO.output(RED_LED_PIN,GPIO.HIGH)
    GPIO.output(GREEN_LED_PIN,GPIO.HIGH)
    GPIO.output(BLUE_LED_PIN,GPIO.HIGH)

# Function to turn RGB LED off
def led_off():
    GPIO.output(RED_LED_PIN,GPIO.LOW)
    GPIO.output(GREEN_LED_PIN,GPIO.LOW)
    GPIO.output(BLUE_LED_PIN,GPIO.LOW)

# Function to track hands
def find_position(frame1):
    landmarks = []
    results = hands.process(cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB))

    if results.multi_hand_landmarks is not None:
        for hand_landmarks in results.multi_hand_landmarks:
            drawingModule.draw_landmarks(frame1, hand_landmarks, handsModule.HAND_CONNECTIONS)

            hand_points = []
            for landmark_id, pt in enumerate(hand_landmarks.landmark):
                x = int(pt.x * FRAME_WIDTH)
                y = int(pt.y * FRAME_HEIGHT)
                hand_points.append([landmark_id, x, y])
            return hand_points
    return landmarks

# Function to determine which finger/s are up
def find_landmark_names(frame1):
    landmarks = []
    results = hands.process(cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB))
    if results.multi_hand_landmarks is not None:
        for handLandmarks in results.multi_hand_landmarks:
            for point in handsModule.HandLandmark:
                 landmarks.append(str(point).replace ("< ","").replace("HandLandmark.", "").replace("_"," ").replace("[]",""))
    return landmarks

# Function to combine bursts
def combine_images(columns, space, images):
    # Determine the dimensions of the composite image.
    rows = len(images) // columns
    if len(images) % columns:
        rows += 1
    width_max = max([Image.open(image).width for image in images])
    height_max = max([Image.open(image).height for image in images])
    background_width = width_max*columns + (space*columns)-space
    background_height = height_max*rows + (space*rows)-space
    background = Image.new('RGBA', (background_width, background_height), (255, 255, 255, 255))
    x = 0
    y = 0
    
    # For Loop takes all burst_# PNGs and lays them out to 2x2 with a row and column gutter of 50px
    for i, image in enumerate(images):
        img = Image.open(image)
        x_offset = int((width_max-img.width)/2)
        y_offset = int((height_max-img.height)/2)
        background.paste(img, (x+x_offset, y+y_offset))
        x += width_max + space
        if (i+1) % columns == 0:
            y += height_max + space
            x = 0
    
    # Below expands the generated background to add outside margins
    bg = Image.new('RGBA', (background_width + space*2, background_height + space*2 + space*4), (255, 255, 255, 255))
    bg.paste(background, (space, space))
    bg_resampled = bg.resize((1430*2,1310*2))
    
    # Below overlays a frame design on bg_resampled depending on chosen frame
    if chosen_frame == 1:
        _, _, _, mask = plain_frame.split()
        bg_resampled.paste(plain_frame, (0,0), mask)
    elif chosen_frame == 2:
        _, _, _, mask = forever_frame.split()
        bg_resampled.paste(forever_frame, (0,0), mask)
    elif chosen_frame == 3:
        _, _, _, mask = blast_frame.split()
        bg_resampled.paste(blast_frame, (0,0), mask)
    elif chosen_frame == 4:
        _, _, _, mask = glowing_frame.split()
        bg_resampled.paste(glowing_frame, (0,0), mask)
    
    # Save final composite to the directory
    bg_resampled.save(
        OUTPUT_DIR / "burst_combined.png",
        "PNG"
    )

# Function to capture image and add an LED Flash indicator for next pose
def capture_image():
    led_white()
    
    # Take current image number and append to file
    global burst_img_counter
    img_name = OUTPUT_DIR / f"burst_{burst_img_counter}.jpg"
    cv2.imwrite(str(img_name), camera_frame)
    burst_img_counter += 1
    
    # Turn LED off
    led_off()

# Add confidence values and extra settings to MediaPipe hand tracking. As we are using a live video stream this is not a static
# image mode, confidence values in regards to overall detection and tracking and we will only let two hands be tracked at the same time
# More hands can be tracked at the same time if desired but will slow down the system
with handsModule.Hands(static_image_mode=False, min_detection_confidence=0.7, min_tracking_confidence=0.7, max_num_hands=1) as hands:

    # Create an infinite loop which will produce the live feed to our desktop and that will search for hands
    while True:
        start_time = time.time()
        ret, frame = cap.read()
        
        # Determines the frame size, 640 x 480 offers a nice balance between speed and accurate identification
        frame1 = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

        # Below is used to determine location of the joints of the fingers
        hand_landmarks = find_position(frame1)
        landmark_names = find_landmark_names(frame1)

        # Below is a series of If statement that will determine if a finger is up or down and
        if len(landmark_names) and len(hand_landmarks)!=0:
            finger=[]
            if hand_landmarks[0][1:] < hand_landmarks[4][1:]: 
               finger.append(1)
            else:
               finger.append(0)   

            fingers=[] 
            for finger_index in range(0,4):
                if hand_landmarks[finger_tip_landmarks[finger_index]][2:] < hand_landmarks[finger_tip_landmarks[finger_index]-2][2:]:
                   fingers.append(1)
                else:
                   fingers.append(0)
        
        # Below will store the number of fingers that are up or down          
        finger_states = fingers + finger
        finger_counts = Counter(finger_states)
        up=finger_counts[1]
        down=finger_counts[0]
        
        # Display instructions, options, and chosen frame to the live video feed
        font = cv2.FONT_HERSHEY_SIMPLEX
        status = f'Chosen Frame: {up}'
        
        cv2.putText(frame1,
                    'Hold Up Finger to Choose Frame:',
                    (20, 30),
                    font, 0.5,
                    (255, 255, 255),
                    2,
                    cv2.LINE_4)
        
        cv2.putText(frame1,
                    '(1) White (2) Green (3) Orange (4) Blue',
                    (20, 60),
                    font, 0.5,
                    (255, 255, 255),
                    2,
                    cv2.LINE_4)

        cv2.putText(frame1,
                    'Close fist to capture',
                    (20, 100),
                    font, 0.5,
                    (255, 255, 255),
                    2,
                    cv2.LINE_4)
        
        cv2.putText(frame1,
                    status,
                    (20,450),
                    font, 0.7,
                    (255, 255, 255),
                    2,
                    cv2.LINE_4)
        
        #Below shows the current frame to the desktop 
        cv2.imshow("Choose Frame", frame1);
        
        # Series of If Statements to store the chosen frame
        # Close hand detection phase when fist is closed (no fingers up detected)
        if up == 1:
            chosen_frame = 1
        elif up == 2:
            chosen_frame = 2
        elif up == 3:
            chosen_frame = 3
        elif up == 4:
            chosen_frame = 4    
        elif up == 0:
            cap.release()
            cv2.destroyAllWindows()
            break
        
        # FPS Optimization codes
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        sleep_time = max(1./DESIRED_FPS - elapsed_time, 0)
        time.sleep(sleep_time)
        
        # Allows the current frame to be shown in the desktop
        key = cv2.waitKey(1) & 0xFF
           
        # Below states that if the |q| is press on the keyboard it will stop the system
        if key == ord("q"):
            cap.release()
            cv2.destroyAllWindows()
            break

# Breathing room before executing the next phase
time.sleep(3)

# Use CV2 Functionality to create a new Video stream and add some values
cam = cv2.VideoCapture(0)

# Start capture countdowns after choosing frame
# Sample: After 10s, capture first burst photo
# Sample: After 15s, capture second burst photo, etc.
timer1 = threading.Timer(10, capture_image)
timer2 = threading.Timer(15, capture_image)
timer3 = threading.Timer(20, capture_image)
timer4 = threading.Timer(25, capture_image)

# Utilized timer threading to not disrupt continuous live video feed
timer1.start()
timer2.start()
timer3.start()
timer4.start()

# Main Photobooth Capture Code
while True:
    ret, camera_frame = cam.read()

    cv2.imshow("Keep Smiling!", camera_frame)
    cv2.waitKey(1)

    # Close the video capture once 4 photos are saved
    if burst_img_counter == 5:
        cam.release()
        cv2.destroyAllWindows()
        break

# Combine burst photos after finishing
combine_images(
    columns=2,
    space=50,
    images=[
        OUTPUT_DIR / "burst_1.jpg",
        OUTPUT_DIR / "burst_2.jpg",
        OUTPUT_DIR / "burst_3.jpg",
        OUTPUT_DIR / "burst_4.jpg",
    ]
)