#Import the necessary Packages for this software to run
import mediapipe
import cv2
from collections import Counter
import math
import time
import threading
from PIL import Image
import RPi.GPIO as GPIO

# Import frame designs
frameOne = Image.open("frame-1-plain_ver.png")
frame2 = Image.open("frame-2-forever_ver.png")
frame3 = Image.open("frame-3-blast_ver.png")
frame4 = Image.open("frame-4-glowing_ver.png")

# Initialize frame choosing variales
img_counter = 1
chosen_frame = 1

# GPIO Initialization
# Disable warnings
GPIO.setwarnings(False)
# Select GPIO Mode
GPIO.setmode(GPIO.BCM)
# Set red, green, and blue pins
redPin = 12
greenPin = 19
bluePin = 13
# Set pins as outputs
GPIO.setup(redPin,GPIO.OUT)
GPIO.setup(greenPin,GPIO.OUT)
GPIO.setup(bluePin,GPIO.OUT)

# Use MediaPipe to draw the hand framework over the top of hands it identifies in Real-Time
drawingModule = mediapipe.solutions.drawing_utils
handsModule = mediapipe.solutions.hands

# Use CV2 Functionality to create a Video stream and add some values
cap = cv2.VideoCapture(0)
tip=[8,12,16,20]
tipname=[8,12,16,20]
fingers=[]
finger=[]
fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')

# Set frame size & FPS
h=480
w=640
desired_fps = 30

# Function to turn RGB LED to white
def white():
    GPIO.output(redPin,GPIO.HIGH)
    GPIO.output(greenPin,GPIO.HIGH)
    GPIO.output(bluePin,GPIO.HIGH)

# Function to turn RGB LED off
def turnOff():
    GPIO.output(redPin,GPIO.LOW)
    GPIO.output(greenPin,GPIO.LOW)
    GPIO.output(bluePin,GPIO.LOW)

# Function to track hands
def findpostion(frame1):
    list=[]
    results = hands.process(cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB))
    if results.multi_hand_landmarks != None:
       for handLandmarks in results.multi_hand_landmarks:
           drawingModule.draw_landmarks(frame1, handLandmarks, handsModule.HAND_CONNECTIONS)
           list=[]
           for id, pt in enumerate (handLandmarks.landmark):
                x = int(pt.x * w)
                y = int(pt.y * h)
                list.append([id,x,y])

    return list

# Function to determine which finger/s are up
def findnameoflandmark(frame1):
    list=[]
    results = hands.process(cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB))
    if results.multi_hand_landmarks != None:
        for handLandmarks in results.multi_hand_landmarks:
            for point in handsModule.HandLandmark:
                 list.append(str(point).replace ("< ","").replace("HandLandmark.", "").replace("_"," ").replace("[]",""))
    return list

# Function to combine bursts
def combine_images(columns, space, images):
    # Below creates a new image based on the dimensions of the captures
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
        _, _, _, mask = frameOne.split()
        bg_resampled.paste(frameOne, (0,0), mask)
    elif chosen_frame == 2:
        _, _, _, mask = frame2.split()
        bg_resampled.paste(frame2, (0,0), mask)
    elif chosen_frame == 3:
        _, _, _, mask = frame3.split()
        bg_resampled.paste(frame3, (0,0), mask)
    elif chosen_frame == 4:
        _, _, _, mask = frame4.split()
        bg_resampled.paste(frame4, (0,0), mask)
    
    # Save final composite to the directory
    bg_resampled.save('burst_combined.png', 'PNG')

# Function to capture image and add an LED Flash indicator for next pose
def capture_img():
    # Turn LED on
    white()
    
    # Take current image number and append to file
    global img_counter
    img_name = f'burst_{img_counter}.jpg'
    
    # Saves a capture of the live feed to the directory then increment counter by 1
    cv2.imwrite(img_name, frame)
    img_counter += 1
    
    # Turn LED off
    turnOff()

# Add confidence values and extra settings to MediaPipe hand tracking. As we are using a live video stream this is not a static
# image mode, confidence values in regards to overall detection and tracking and we will only let two hands be tracked at the same time
# More hands can be tracked at the same time if desired but will slow down the system
with handsModule.Hands(static_image_mode=False, min_detection_confidence=0.7, min_tracking_confidence=0.7, max_num_hands=1) as hands:

    # Create an infinite loop which will produce the live feed to our desktop and that will search for hands
    while True:
        start_time = time.time()
        ret, frame = cap.read()
        
        # Determines the frame size, 640 x 480 offers a nice balance between speed and accurate identification
        frame1 = cv2.resize(frame, (w, h))

        # Below is used to determine location of the joints of the fingers
        a=findpostion(frame1)
        b=findnameoflandmark(frame1)

        # Below is a series of If statement that will determine if a finger is up or down and
        if len(b and a)!=0:
            finger=[]
            if a[0][1:] < a[4][1:]: 
               finger.append(1)
            else:
               finger.append(0)   

            fingers=[] 
            for id in range(0,4):
                if a[tip[id]][2:] < a[tip[id]-2][2:]:
                   fingers.append(1)
                else:
                   fingers.append(0)
        
        # Below will store the number of fingers that are up or down          
        x= fingers + finger
        c= Counter(x)
        up=c[1]
        down=c[0]
        
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
        
        sleep_time = max(1./desired_fps - elapsed_time, 0)
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
timer1 = threading.Timer(10, capture_img)
timer2 = threading.Timer(15, capture_img)
timer3 = threading.Timer(20, capture_img)
timer4 = threading.Timer(25, capture_img)

# Utilized timer threading to not disrupt continuous live video feed
timer1.start()
timer2.start()
timer3.start()
timer4.start()

# Main Photobooth Capture Code
while True:
    ret, frame = cam.read()
    
    cv2.imshow("Keep Smiling!", frame)
    cv2.waitKey(1)

    # Close the video capture once 4 photos are saved
    if img_counter == 5:
        cam.release()
        cv2.destroyAllWindows()
        break

# Combine burst photos after finishing
combine_images(columns=2, space=50, images=['burst_1.jpg', 'burst_2.jpg', 'burst_3.jpg', 'burst_4.jpg'])